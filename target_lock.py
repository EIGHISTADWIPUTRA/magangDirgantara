"""Target locking pipeline optimized for Raspberry Pi 4B.

Implements a 3-thread pipeline:
1) Producer: capture frames continuously.
2) AI Consumer: run YOLO with inference-skip + lightweight tracker update.
3) Visualizer/Control: render latest state and publish lock/control info.

Default strategy:
- Camera index: 0
- Input size: 320 (can be 416)
- Inference skip: run YOLO every 3 frames (1 detect + 2 predict)
"""

import argparse
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2

from modules.kamera import WebcamStream
from modules.detektor import YoloDetektor


BBox = Tuple[int, int, int, int]


@dataclass
class Track:
    """Single lightweight track state."""

    track_id: int
    bbox: BBox
    cls_id: int
    conf: float
    hits: int = 1
    age: int = 0
    last_seen_frame: int = 0


class LightTracker:
    """Lightweight IOU tracker inspired by SORT-style lifecycle.

    This tracker is intentionally simple for Raspberry Pi CPU usage.
    - On detect frames: associate detections by IoU.
    - On skip frames: keep previous box (cheap prediction surrogate).
    - Remove stale tracks based on max_age.
    - Consider track stable when hits >= min_hits.
    """

    def __init__(self, max_age: int = 5, min_hits: int = 2, iou_threshold: float = 0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.tracks: List[Track] = []
        self._next_id = 1

    @staticmethod
    def _iou(a: BBox, b: BBox) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        iw = max(0, inter_x2 - inter_x1)
        ih = max(0, inter_y2 - inter_y1)
        inter = iw * ih

        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        if union <= 0:
            return 0.0
        return inter / union

    def _match(self, detections: List[Tuple[BBox, int, float]], frame_idx: int) -> None:
        used_det = set()

        for t in self.tracks:
            best_iou = 0.0
            best_j = -1
            for j, (dbox, dcls, dconf) in enumerate(detections):
                if j in used_det:
                    continue
                if dcls != t.cls_id:
                    continue
                score = self._iou(t.bbox, dbox)
                if score > best_iou:
                    best_iou = score
                    best_j = j

            if best_j >= 0 and best_iou >= self.iou_threshold:
                dbox, dcls, dconf = detections[best_j]
                t.bbox = dbox
                t.conf = dconf
                t.hits += 1
                t.age = 0
                t.last_seen_frame = frame_idx
                used_det.add(best_j)
            else:
                t.age += 1

        for j, (dbox, dcls, dconf) in enumerate(detections):
            if j in used_det:
                continue
            self.tracks.append(
                Track(
                    track_id=self._next_id,
                    bbox=dbox,
                    cls_id=dcls,
                    conf=dconf,
                    hits=1,
                    age=0,
                    last_seen_frame=frame_idx,
                )
            )
            self._next_id += 1

        self.tracks = [t for t in self.tracks if t.age <= self.max_age]

    def update_detect(self, detections: List[Tuple[BBox, int, float]], frame_idx: int) -> List[Track]:
        self._match(detections, frame_idx)
        return self.get_active_tracks()

    def update_predict(self) -> List[Track]:
        for t in self.tracks:
            t.age += 1
        self.tracks = [t for t in self.tracks if t.age <= self.max_age]
        return self.get_active_tracks()

    def get_active_tracks(self) -> List[Track]:
        return [t for t in self.tracks if t.hits >= self.min_hits]


@dataclass
class SharedState:
    """Shared state exchanged between pipeline threads."""

    latest_frame: Optional[object] = None
    frame_idx: int = 0
    tracks: Optional[List[Track]] = None
    yolo_ran: bool = False
    ai_fps: int = 0
    vis_fps: int = 0
    lock_status: str = "NO LOCK"


class TargetLockPipeline:
    """End-to-end target lock pipeline for RPi optimization strategy."""

    def __init__(
        self,
        model_path: str,
        target_label: str,
        camera_index: int = 0,
        input_size: int = 320,
        skip_n: int = 3,
        max_age: int = 5,
        min_hits: int = 2,
        conf_threshold: float = 0.35,
    ):
        self.model_path = model_path
        self.target_label = target_label.strip().lower()
        self.camera_index = camera_index
        self.input_size = input_size
        self.skip_n = max(1, skip_n)
        self.conf_threshold = conf_threshold

        self.tracker = LightTracker(max_age=max_age, min_hits=min_hits, iou_threshold=0.3)

        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self.state_lock = threading.Lock()
        self.state = SharedState(tracks=[])
        self.stop_event = threading.Event()

        self.camera: Optional[WebcamStream] = None
        self.detector: Optional[YoloDetektor] = None

    def _safe_put_latest(self, item) -> None:
        while True:
            try:
                self.frame_queue.put_nowait(item)
                return
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    return

    def producer_loop(self) -> None:
        """Thread A: capture latest frame continuously."""
        try:
            self.camera = WebcamStream(self.camera_index, self.input_size, self.input_size)
            if not self.camera.siap():
                print("[x] Kamera tidak siap")
                self.stop_event.set()
                return

            while not self.stop_event.is_set():
                ret, frame = self.camera.get_frame()
                if not ret or frame is None:
                    continue

                with self.state_lock:
                    self.state.latest_frame = frame

                ts = time.time()
                self._safe_put_latest((frame, ts))
        except Exception as e:
            print(f"[x] Producer error: {e}")
            self.stop_event.set()
        finally:
            if self.camera is not None:
                try:
                    self.camera.berhenti()
                except Exception:
                    pass

    def _extract_detections(self, results) -> List[Tuple[BBox, int, float]]:
        detections: List[Tuple[BBox, int, float]] = []
        for label in results:
            boxes = getattr(label, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                try:
                    conf = float(box.conf[0])
                    if conf < self.conf_threshold:
                        continue
                    cls_id = int(box.cls[0])
                    name = str(self.detector.kelas.get(cls_id, "")).lower()
                    if self.target_label and name != self.target_label:
                        continue
                    x1, y1, x2, y2 = box.xyxy[0]
                    detections.append(((int(x1), int(y1), int(x2), int(y2)), cls_id, conf))
                except Exception:
                    continue
        return detections

    def ai_loop(self) -> None:
        """Thread B: inference-skip + tracker updates."""
        try:
            self.detector = YoloDetektor(self.model_path)
        except Exception as e:
            print(f"[x] AI init error: {e}")
            self.stop_event.set()
            return

        frame_idx = 0
        last_time = time.perf_counter()
        ai_dt_smooth = 0.0  # EMA untuk Delta Time, bukan FPS
        max_ai_fps = 120.0

        while not self.stop_event.is_set():
            try:
                frame, _ = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            frame_idx += 1
            run_yolo = (frame_idx % self.skip_n) == 1

            if run_yolo:
                try:
                    results = list(self.detector.prediksi(frame))
                    detections = self._extract_detections(results)
                    tracks = self.tracker.update_detect(detections, frame_idx)
                except Exception as e:
                    print(f"[!] AI detect error: {e}")
                    tracks = self.tracker.update_predict()
                    run_yolo = False
            else:
                tracks = self.tracker.update_predict()

            now = time.perf_counter()
            dt = max(now - last_time, 1e-6)
            
            # EMA pada Delta Time agar FPS akurat merepresentasikan rata-rata throughput
            if ai_dt_smooth == 0.0:
                ai_dt_smooth = dt
            else:
                ai_dt_smooth = (ai_dt_smooth * 0.85) + (dt * 0.15)
            
            ai_fps = int(min(1.0 / ai_dt_smooth, max_ai_fps))
            last_time = now

            lock_status = "LOCK" if len(tracks) > 0 else "NO LOCK"

            with self.state_lock:
                self.state.frame_idx = frame_idx
                self.state.tracks = list(tracks)
                self.state.yolo_ran = run_yolo
                self.state.ai_fps = ai_fps
                self.state.lock_status = lock_status

    def _draw_overlay(self, frame, tracks: List[Track], yolo_ran: bool, ai_fps: int, vis_fps: int, lock_status: str):
        for t in tracks:
            x1, y1, x2, y2 = t.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(
                frame,
                f"ID {t.track_id} conf {t.conf:.2f}",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 220, 0),
                2,
            )

        mode = "YOLO" if yolo_ran else "PREDICT"
        cv2.putText(frame, f"Mode: {mode}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, f"AI FPS: {ai_fps}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 220, 0), 2)
        cv2.putText(frame, f"VIS FPS: {vis_fps}", (10, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 220, 0), 2)
        cv2.putText(frame, f"Lock: {lock_status}", (10, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if lock_status == "LOCK" else (0, 0, 255), 2)

    def _control_stub(self, tracks: List[Track], frame_shape) -> None:
        """Thread C control hook: compute center error (can be sent to servo)."""
        if not tracks:
            return
        h, w = frame_shape[:2]
        cx_frame = w // 2
        cy_frame = h // 2

        best = max(tracks, key=lambda t: t.conf)
        x1, y1, x2, y2 = best.bbox
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        err_x = cx - cx_frame
        err_y = cy - cy_frame

        # Placeholder: replace with motor/servo command publishing.
        _ = (err_x, err_y)

    def visualizer_loop(self) -> None:
        """Thread C: render + control update at high perceived refresh."""
        target_vis_fps = 24.0
        min_vis_dt = 1.0 / target_vis_fps
        last_vis = time.perf_counter()
        vis_dt_smooth = 0.0  # EMA untuk Delta Time Visualizer
        max_vis_fps = 120.0

        while not self.stop_event.is_set():
            loop_start = time.perf_counter()

            with self.state_lock:
                frame = None if self.state.latest_frame is None else self.state.latest_frame.copy()
                tracks = list(self.state.tracks or [])
                yolo_ran = self.state.yolo_ran
                ai_fps = self.state.ai_fps
                lock_status = self.state.lock_status

            if frame is None:
                time.sleep(0.005)
                continue

            now = time.perf_counter()
            vis_dt = max(now - last_vis, 1e-6)
            
            if vis_dt_smooth == 0.0:
                vis_dt_smooth = vis_dt
            else:
                vis_dt_smooth = (vis_dt_smooth * 0.85) + (vis_dt * 0.15)
                
            vis_fps = int(min(1.0 / vis_dt_smooth, max_vis_fps))
            last_vis = now

            self._control_stub(tracks, frame.shape)
            self._draw_overlay(frame, tracks, yolo_ran, ai_fps, vis_fps, lock_status)

            cv2.imshow("Target Lock Pipeline", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                self.stop_event.set()
                break

            with self.state_lock:
                self.state.vis_fps = vis_fps

            # Limit render loop speed so VIS FPS stays realistic and stable.
            spent = time.perf_counter() - loop_start
            remain = min_vis_dt - spent
            if remain > 0:
                time.sleep(remain)

    def run(self) -> int:
        if not os.path.exists(self.model_path):
            print(f"[x] Model path tidak ditemukan: {self.model_path}")
            return 1

        producer = threading.Thread(target=self.producer_loop, daemon=True)
        ai_worker = threading.Thread(target=self.ai_loop, daemon=True)
        visualizer = threading.Thread(target=self.visualizer_loop, daemon=True)

        producer.start()
        ai_worker.start()
        visualizer.start()

        try:
            while not self.stop_event.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop_event.set()

        producer.join(timeout=1.5)
        ai_worker.join(timeout=1.5)
        visualizer.join(timeout=1.5)
        cv2.destroyAllWindows()
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Target lock pipeline for Raspberry Pi 4B")
    parser.add_argument(
        "--model",
        default="/home/eighista/Documents/MAGANG/models/model_yolo/yolo11n_ncnn_model",
        #default="/home/eighista/Documents/MAGANG/finalCode/models/yolo_ncnn_model",
        help="Path model YOLO (pt / tflite / ncnn directory)",
    )
    parser.add_argument("--target", default="person", help="Nama target class (contoh: person)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--size", type=int, choices=[320, 416], default=416, help="Input width/height")
    parser.add_argument("--skip", type=int, default=3, help="Jalankan YOLO setiap N frame")
    parser.add_argument("--max-age", type=int, default=5, help="Hapus track jika hilang > max_age frame")
    parser.add_argument("--min-hits", type=int, default=2, help="Track valid setelah min_hits")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    pipeline = TargetLockPipeline(
        model_path=args.model,
        target_label=args.target,
        camera_index=args.camera,
        input_size=args.size,
        skip_n=args.skip,
        max_age=args.max_age,
        min_hits=args.min_hits,
        conf_threshold=args.conf,
    )
    return pipeline.run()


if __name__ == "__main__":
    raise SystemExit(main())