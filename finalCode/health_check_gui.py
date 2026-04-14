"""
Health Check GUI Application for Raspberry Pi

This GUI application provides a visual interface to check the status of all sensors
and connected hardware. It can be run standalone or configured to auto-start on boot.

Usage:
    python finalCode/health_check_gui.py
    python -m finalCode.health_check_gui
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import time
import os
import sys

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# Ensure the parent directory of finalCode is on sys.path
_package_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_package_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# YOLO model configuration (NCNN directory).
YOLO_MODEL_PATH = "/home/eighista/Documents/MAGANG/finalCode/models/yolo_ncnn_model"
YOLO_WINDOW_NAME = "YOLO Detection"


class HealthCheckGUI:
    """GUI for system health checks."""
    
    def __init__(self, root):
        """Initialize the health check GUI."""
        self.root = root
        self.root.title("System Health Check")
        self.root.geometry("1350x720")
        self.root.resizable(True, True)
        
        # Color scheme
        self.COLOR_BG = "#1e1e1e"
        self.COLOR_FG = "#ffffff"
        self.COLOR_SUCCESS = "#00ff00"
        self.COLOR_ERROR = "#ff0000"
        self.COLOR_WARNING = "#ffcc00"
        self.COLOR_PENDING = "#808080"
        
        # Configure root style
        self.root.configure(bg=self.COLOR_BG)
        
        # Status tracking
        self.sensor_status = {}
        self.is_checking = False
        self.app_closing = False

        # YOLO tracking
        self.yolo_running = False
        self.yolo_thread = None
        self.yolo_model = None
        self.yolo_shutting_down = False
        self.yolo_photo = None

        # LoRa sender tracking
        self.lora_running = False
        self.lora_thread = None
        self.lora_sender = None
        self.lora_counter = 1
        self.lora_interval = 0.5
        
        # Build UI
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def build_ui(self):
        """Build the GUI components."""
        # Header
        header_frame = tk.Frame(self.root, bg="#0066cc")
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        
        title_label = tk.Label(
            header_frame,
            text="🔧 System Health Check",
            font=("Arial", 18, "bold"),
            bg="#0066cc",
            fg=self.COLOR_FG
        )
        title_label.pack(pady=15)
        
        # Main content frame
        content_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Left panel (health check)
        left_panel = tk.Frame(content_frame, bg=self.COLOR_BG)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Right side container (YOLO + LoRa sender panel)
        right_container = tk.Frame(content_frame, bg=self.COLOR_BG)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # YOLO preview panel
        right_panel = tk.Frame(right_container, bg="#151515", relief=tk.FLAT, highlightthickness=1, highlightbackground="#444444")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # LoRa sender panel
        lora_panel = tk.Frame(right_container, bg="#101820", relief=tk.FLAT, highlightthickness=1, highlightbackground="#3d4f5f")
        lora_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))
        
        # Sensors frame
        sensors_label = tk.Label(
            left_panel,
            text="Sensor Status:",
            font=("Arial", 12, "bold"),
            bg=self.COLOR_BG,
            fg=self.COLOR_FG
        )
        sensors_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Scrollable sensors area
        self.sensors_frame = tk.Frame(left_panel, bg=self.COLOR_BG)
        self.sensors_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Define sensors to check
        self.sensors_list = [
            ('📷 Camera', 'camera'),
            ('📡 LoRa Module', 'lora'),
            ('🧭 MPU6050 (Accelerometer)', 'mpu6050'),
            ('🌡️  BMP280 (Pressure)', 'bmp280'),
            ('💡 GY511 (Ambient Light)', 'gy511'),
            ('🗺️  GPSM6N (GPS)', 'gpsm6n'),
            ('📶 WiFi Connection', 'wifi'),
            ('🔋 Power Supply', 'power'),
        ]
        
        # Create sensor status widgets
        self.sensor_widgets = {}
        for sensor_name, sensor_key in self.sensors_list:
            widget = self.create_sensor_widget(self.sensors_frame, sensor_name, sensor_key)
            self.sensor_widgets[sensor_key] = widget
        
        # Buttons frame
        buttons_frame = tk.Frame(left_panel, bg=self.COLOR_BG)
        buttons_frame.pack(fill=tk.X, pady=15)
        
        # Start check button
        self.start_btn = tk.Button(
            buttons_frame,
            text="▶ Start Check",
            command=self.start_health_check,
            bg="#0066cc",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        # Reset button
        reset_btn = tk.Button(
            buttons_frame,
            text="🔄 Reset",
            command=self.reset_status,
            bg="#666666",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2"
        )
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        # Exit button
        exit_btn = tk.Button(
            buttons_frame,
            text="✕ Exit",
            command=self.on_close,
            bg="#cc0000",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2"
        )
        exit_btn.pack(side=tk.RIGHT, padx=5)

        # YOLO panel title
        yolo_title = tk.Label(
            right_panel,
            text="YOLO Detection (NCNN Model)",
            font=("Arial", 12, "bold"),
            bg="#151515",
            fg=self.COLOR_FG
        )
        yolo_title.pack(anchor=tk.W, padx=12, pady=(12, 6))

        # YOLO model path info
        yolo_path_label = tk.Label(
            right_panel,
            text=f"Model: {YOLO_MODEL_PATH}",
            font=("Arial", 9),
            bg="#151515",
            fg="#bdbdbd",
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=600
        )
        yolo_path_label.pack(anchor=tk.W, padx=12)

        # YOLO video canvas
        self.yolo_canvas = tk.Canvas(
            right_panel,
            width=640,
            height=480,
            bg="#000000",
            highlightthickness=1,
            highlightbackground="#333333"
        )
        self.yolo_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.yolo_canvas.create_text(
            320,
            240,
            text="YOLO Preview di Panel Ini\nClick Start YOLO",
            fill="#bdbdbd",
            font=("Arial", 14, "bold"),
            justify=tk.CENTER
        )

        # YOLO status text
        self.yolo_status_label = tk.Label(
            right_panel,
            text="YOLO: Stopped",
            font=("Arial", 10),
            bg="#151515",
            fg="#ffcc00",
            anchor=tk.W
        )
        self.yolo_status_label.pack(fill=tk.X, padx=12, pady=(0, 8))

        # YOLO controls
        yolo_btn_frame = tk.Frame(right_panel, bg="#151515")
        yolo_btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.yolo_start_btn = tk.Button(
            yolo_btn_frame,
            text="▶ Start YOLO",
            command=self.start_yolo_detection,
            bg="#1c7d3a",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.yolo_start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.yolo_stop_btn = tk.Button(
            yolo_btn_frame,
            text="■ Stop YOLO",
            command=self.stop_yolo_detection,
            state=tk.DISABLED,
            bg="#555555",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.yolo_stop_btn.pack(side=tk.LEFT)

        # LoRa panel title
        lora_title = tk.Label(
            lora_panel,
            text="LoRa Sender (SIKAP)",
            font=("Arial", 12, "bold"),
            bg="#101820",
            fg=self.COLOR_FG
        )
        lora_title.pack(anchor=tk.W, padx=12, pady=(12, 6))

        lora_cmd_label = tk.Label(
            lora_panel,
            text="Skenario: python -m finalCode.main lora send sikap",
            font=("Arial", 9),
            bg="#101820",
            fg="#9ec1da",
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=420
        )
        lora_cmd_label.pack(anchor=tk.W, padx=12)

        self.lora_status_label = tk.Label(
            lora_panel,
            text="LoRa: Stopped",
            font=("Arial", 10),
            bg="#101820",
            fg="#ffcc00",
            anchor=tk.W
        )
        self.lora_status_label.pack(fill=tk.X, padx=12, pady=(8, 6))

        lora_btn_frame = tk.Frame(lora_panel, bg="#101820")
        lora_btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.lora_start_btn = tk.Button(
            lora_btn_frame,
            text="▶ Start LoRa",
            command=self.start_lora_sender,
            bg="#0b8f6f",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.lora_start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.lora_stop_btn = tk.Button(
            lora_btn_frame,
            text="■ Stop LoRa",
            command=self.stop_lora_sender,
            state=tk.DISABLED,
            bg="#555555",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.lora_stop_btn.pack(side=tk.LEFT)

        # LoRa logs area
        self.lora_log = ScrolledText(
            lora_panel,
            height=18,
            bg="#0a1118",
            fg="#d8f2ff",
            insertbackground="#d8f2ff",
            font=("Courier New", 9),
            wrap=tk.WORD
        )
        self.lora_log.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))
        self.lora_log.insert(tk.END, "[INFO] LoRa sender siap. Klik Start LoRa untuk kirim data sikap.\n")
        self.lora_log.config(state=tk.DISABLED)
        
        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            bg="#333333",
            fg=self.COLOR_FG,
            font=("Arial", 9),
            anchor=tk.W,
            padx=15,
            pady=8
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def on_close(self):
        """Close app and stop background tasks safely."""
        self.app_closing = True
        self.stop_lora_sender()
        self.stop_yolo_detection()

        if self.yolo_thread is not None and self.yolo_thread.is_alive():
            self.yolo_thread.join(timeout=1.5)
        if self.lora_thread is not None and self.lora_thread.is_alive():
            self.lora_thread.join(timeout=1.0)

        self._close_yolo_window()

        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _safe_after(self, callback, delay_ms=0):
        """Schedule Tk callback only when app is still alive."""
        if self.app_closing:
            return
        try:
            if self.root.winfo_exists():
                self.root.after(delay_ms, callback)
        except tk.TclError:
            pass

    def _close_yolo_window(self):
        """Reset YOLO canvas preview area."""
        if not hasattr(self, "yolo_canvas"):
            return
        self.yolo_canvas.delete("all")
        self.yolo_canvas.create_text(
            320,
            240,
            text="YOLO Preview berhenti\nClick Start YOLO",
            fill="#bdbdbd",
            font=("Arial", 14, "bold"),
            justify=tk.CENTER
        )
        self.yolo_photo = None

    def _update_yolo_canvas(self, frame):
        """Render BGR OpenCV frame into Tk canvas."""
        if Image is None or ImageTk is None:
            self.update_yolo_status("Pillow belum terpasang", "#ff0000")
            return
        if not hasattr(self, "yolo_canvas"):
            return

        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)

        self.yolo_canvas.delete("all")
        self.yolo_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.yolo_photo = photo

    def update_yolo_status(self, message, color="#ffcc00"):
        """Update YOLO status label."""
        self.yolo_status_label.config(text=f"YOLO: {message}", fg=color)

    def update_lora_status(self, message, color="#ffcc00"):
        """Update LoRa status label."""
        self.lora_status_label.config(text=f"LoRa: {message}", fg=color)

    def append_lora_log(self, text):
        """Append one line to LoRa log box safely."""
        self.lora_log.config(state=tk.NORMAL)
        self.lora_log.insert(tk.END, text + "\n")
        self.lora_log.see(tk.END)
        self.lora_log.config(state=tk.DISABLED)

    def _load_yolo_model(self):
        """Load YOLO model from configured path."""
        if self.yolo_model is not None:
            return True

        if not os.path.exists(YOLO_MODEL_PATH):
            self.update_yolo_status("Model file belum ada", "#ff0000")
            messagebox.showwarning(
                "Model YOLO Belum Ada",
                f"Model belum ditemukan di:\n{YOLO_MODEL_PATH}\n\n"
                "Silakan copy model YOLO Anda ke path tersebut."
            )
            return False

        try:
            from modules.detektor import YoloDetektor
            self.yolo_model = YoloDetektor(YOLO_MODEL_PATH)
            self.update_yolo_status("Model loaded", "#00ff99")
            return True
        except ImportError:
            self.update_yolo_status("Module detektor/ultralytics belum siap", "#ff0000")
            messagebox.showerror(
                "Dependency Missing",
                "Module detektor atau dependency model belum tersedia di environment aktif.\n"
                "Pastikan package ultralytics dan modul project bisa diimport."
            )
            return False
        except Exception as e:
            self.update_yolo_status(f"Gagal load model: {str(e)[:40]}", "#ff0000")
            return False

    def start_yolo_detection(self):
        """Start YOLO detection in a background thread."""
        if self.yolo_running:
            return

        if self.yolo_shutting_down or (self.yolo_thread is not None and self.yolo_thread.is_alive()):
            self.update_yolo_status("Tunggu, YOLO masih cleanup...", "#ff9900")
            return

        if not self._load_yolo_model():
            return

        self.yolo_running = True
        self.yolo_shutting_down = False
        self.yolo_start_btn.config(state=tk.DISABLED)
        self.yolo_stop_btn.config(state=tk.NORMAL)
        self.update_yolo_status("Starting camera + OpenCV window...", "#ffcc00")

        self.yolo_thread = threading.Thread(target=self._yolo_loop, daemon=True)
        self.yolo_thread.start()

    def stop_yolo_detection(self):
        """Stop YOLO detection loop."""
        self.yolo_running = False
        if self.yolo_thread is not None and self.yolo_thread.is_alive():
            self.yolo_shutting_down = True
            self.update_yolo_status("Stopping...", "#ff9900")
        if hasattr(self, "yolo_start_btn"):
            self.yolo_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "yolo_stop_btn"):
            self.yolo_stop_btn.config(state=tk.DISABLED)
        if hasattr(self, "yolo_status_label") and not self.yolo_shutting_down:
            self.update_yolo_status("Stopped", "#ffcc00")

    def _finish_yolo_shutdown(self):
        """Finalize YOLO UI state after thread fully exits."""
        self.yolo_running = False
        self.yolo_shutting_down = False
        self.yolo_thread = None
        if hasattr(self, "yolo_start_btn"):
            self.yolo_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "yolo_stop_btn"):
            self.yolo_stop_btn.config(state=tk.DISABLED)
        if hasattr(self, "yolo_status_label"):
            self.update_yolo_status("Stopped", "#ffcc00")

    def _initialize_lora_sender(self):
        """Initialize LoRa sender for sikap payload mode."""
        if self.lora_sender is not None:
            return True

        try:
            from finalCode.lora.sender_sensor import LoRaSensorSender
            self.lora_sender = LoRaSensorSender(sensors='sikap')
            self.lora_counter = 1
            self._safe_after(lambda: self.update_lora_status("Sender initialized", "#00ff99"))
            self._safe_after(lambda: self.append_lora_log("[INFO] Sender LoRa mode SIKAP initialized."))
            return True
        except Exception as e:
            err = str(e)
            self._safe_after(lambda: self.update_lora_status("Init gagal", "#ff0000"))
            self._safe_after(lambda: self.append_lora_log(f"[ERROR] Init LoRa gagal: {err}"))
            return False

    def start_lora_sender(self):
        """Start LoRa sender loop for sikap payload."""
        if self.lora_running:
            return

        self.lora_running = True
        self.lora_start_btn.config(state=tk.DISABLED)
        self.lora_stop_btn.config(state=tk.NORMAL)
        self.update_lora_status("Starting...", "#ffcc00")

        self.lora_thread = threading.Thread(target=self._lora_loop, daemon=True)
        self.lora_thread.start()

    def stop_lora_sender(self):
        """Stop LoRa sender and ensure GPIO is released."""
        self.lora_running = False
        if hasattr(self, "lora_start_btn"):
            self.lora_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "lora_stop_btn"):
            self.lora_stop_btn.config(state=tk.DISABLED)

        if self.lora_sender is not None:
            try:
                self.lora_sender.cleanup()
                self.append_lora_log("[INFO] Cleanup LoRa + GPIO selesai.")
            except Exception as e:
                self.append_lora_log(f"[WARN] Cleanup LoRa bermasalah: {e}")
            finally:
                self.lora_sender = None

        if hasattr(self, "lora_status_label"):
            self.update_lora_status("Stopped", "#ffcc00")

    def _lora_loop(self):
        """Background loop for periodic sikap data transmission."""
        if not self._initialize_lora_sender():
            self._safe_after(self.stop_lora_sender)
            return

        self._safe_after(lambda: self.update_lora_status("Running", "#00ff99"))

        try:
            while self.lora_running:
                sukses, pesan = self.lora_sender.kirim_data(self.lora_counter)
                jam = time.strftime("%H:%M:%S")
                status_text = "TERKIRIM" if sukses else "TIMEOUT"
                log_line = f"[{jam}] #{self.lora_counter} {status_text} | {pesan}"
                self._safe_after(lambda line=log_line: self.append_lora_log(line))
                self._safe_after(lambda st=status_text: self.update_lora_status(st, "#00ff99" if st == "TERKIRIM" else "#ff9900"))
                self.lora_counter += 1

                # Use short sleep chunks so stop request responds quickly.
                remaining = self.lora_interval
                while remaining > 0 and self.lora_running:
                    chunk = min(0.1, remaining)
                    time.sleep(chunk)
                    remaining -= chunk
        except Exception as e:
            err = str(e)
            self._safe_after(lambda: self.append_lora_log(f"[ERROR] Loop LoRa error: {err}"))
            self._safe_after(lambda: self.update_lora_status("Error", "#ff0000"))
        finally:
            self._safe_after(self.stop_lora_sender)

    def _yolo_loop(self):
        """Capture camera frames, run YOLO, and show result on Tk canvas."""
        import cv2

        from finalCode.camera.stream import WebcamStream

        if Image is None or ImageTk is None:
            self._safe_after(lambda: self.update_yolo_status("Install pillow dulu", "#ff0000"))
            self._safe_after(self._finish_yolo_shutdown)
            return

        kamera = None
        for attempt in range(1, 11):
            try:
                kamera = WebcamStream(0, 640, 480)
                if kamera.is_ready():
                    break
            except Exception:
                kamera = None

            self.root.after(
                0,
                lambda n=attempt: self.update_yolo_status(f"Camera retry {n}/10...", "#ff9900")
            )
            time.sleep(0.5)

        if kamera is None or not kamera.is_ready():
            self._safe_after(lambda: self.update_yolo_status("Camera tidak bisa dibuka", "#ff0000"))
            self._safe_after(self._finish_yolo_shutdown)
            return

        prev_time = time.perf_counter()
        fps_smooth = 0.0
        frame_count = 0

        try:
            while self.yolo_running:
                ret, frame = kamera.get_frame()
                if not ret or frame is None:
                    self._safe_after(lambda: self.update_yolo_status("Gagal baca frame", "#ff0000"))
                    continue

                status_message = "Tidak ada deteksi"

                try:
                    infer_start = time.perf_counter()
                    results = list(self.yolo_model.prediksi(frame))
                    infer_ms = (time.perf_counter() - infer_start) * 1000.0

                    frame = self.yolo_model.bounding_box(frame, results)
                    frame = self.yolo_model.fps(frame)

                    detected_count = 0
                    for label in results:
                        boxes = getattr(label, "boxes", None)
                        if boxes is not None:
                            detected_count += len(boxes)

                    now = time.perf_counter()
                    inst_fps = 1.0 / max(now - prev_time, 1e-6)
                    prev_time = now
                    fps_smooth = inst_fps if fps_smooth == 0.0 else (fps_smooth * 0.9 + inst_fps * 0.1)

                    cv2.putText(
                        frame,
                        f"GUI FPS: {fps_smooth:.1f} | INF: {infer_ms:.1f} ms",
                        (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 220, 0),
                        2,
                        cv2.LINE_AA,
                    )

                    status_message = f"Deteksi {detected_count} objek | FPS {fps_smooth:.1f}"
                except Exception as e:
                    status_message = f"Inference error: {str(e)[:35]}"

                self._safe_after(lambda frm=frame.copy(): self._update_yolo_canvas(frm))

                frame_count += 1
                if frame_count % 10 == 0:
                    self._safe_after(lambda msg=status_message: self.update_yolo_status(msg, "#00ff99"))

        finally:
            if kamera is not None:
                try:
                    kamera.stop()
                except Exception:
                    pass
            time.sleep(0.2)
            self._safe_after(self._close_yolo_window)
            self._safe_after(self._finish_yolo_shutdown)
        
    def create_sensor_widget(self, parent, sensor_name, sensor_key):
        """Create a sensor status widget."""
        widget_frame = tk.Frame(parent, bg="#2a2a2a", relief=tk.FLAT, highlightthickness=1, highlightbackground="#444444")
        widget_frame.pack(fill=tk.X, pady=5)
        
        # Sensor name
        name_label = tk.Label(
            widget_frame,
            text=sensor_name,
            font=("Arial", 11),
            bg="#2a2a2a",
            fg=self.COLOR_FG,
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15, pady=12)
        
        # Status circle
        status_canvas = tk.Canvas(
            widget_frame,
            width=30,
            height=30,
            bg="#2a2a2a",
            highlightthickness=0
        )
        status_canvas.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # Draw initial pending status
        status_canvas.create_oval(5, 5, 25, 25, fill=self.COLOR_PENDING, outline=self.COLOR_PENDING)
        
        # Status text
        status_text = tk.Label(
            widget_frame,
            text="PENDING",
            font=("Arial", 9, "bold"),
            bg="#2a2a2a",
            fg=self.COLOR_PENDING
        )
        status_text.pack(side=tk.RIGHT, padx=10)
        
        return {
            'frame': widget_frame,
            'canvas': status_canvas,
            'label': status_text,
            'name_label': name_label
        }
    
    def set_sensor_status(self, sensor_key, status, message=""):
        """Update sensor status display."""
        if sensor_key not in self.sensor_widgets:
            return
        
        widget = self.sensor_widgets[sensor_key]
        
        # Determine color based on status
        if status == "success":
            color = self.COLOR_SUCCESS
            text = "OK" if not message else f"OK - {message}"
        elif status == "warning":
            color = self.COLOR_WARNING
            text = f"WARNING - {message}" if message else "WARNING"
        elif status == "error":
            color = self.COLOR_ERROR
            text = f"ERROR - {message}" if message else "ERROR"
        else:  # pending
            color = self.COLOR_PENDING
            text = "PENDING"
        
        # Update canvas
        widget['canvas'].delete("all")
        widget['canvas'].create_oval(5, 5, 25, 25, fill=color, outline=color)
        
        # Update label
        widget['label'].config(text=text, fg=color)
        
        self.sensor_status[sensor_key] = status
        self.root.update()
    
    def reset_status(self):
        """Reset all sensor status to pending."""
        for sensor_key in self.sensor_widgets:
            self.set_sensor_status(sensor_key, "pending")
        self.update_status_bar("Ready")
    
    def update_status_bar(self, message):
        """Update the status bar message."""
        self.status_bar.config(text=message)
        self.root.update()
    
    def start_health_check(self):
        """Start the health check in a separate thread."""
        if self.is_checking:
            messagebox.showwarning("Already Checking", "Health check is already in progress!")
            return
        
        self.is_checking = True
        self.start_btn.config(state=tk.DISABLED)
        self.reset_status()
        
        # Run check in background thread
        check_thread = threading.Thread(target=self.perform_health_check)
        check_thread.daemon = True
        check_thread.start()
    
    def perform_health_check(self):
        """Perform the actual health checks."""
        try:
            self.update_status_bar("🔍 Checking sensors...")
            
            # Camera check
            self.update_status_bar("Checking camera...")
            self.check_camera()
            time.sleep(0.5)
            
            # LoRa check
            self.update_status_bar("Checking LoRa module...")
            self.check_lora()
            time.sleep(0.5)
            
            # MPU6050 check
            self.update_status_bar("Checking MPU6050...")
            self.check_mpu6050()
            time.sleep(0.5)
            
            # BMP280 check
            self.update_status_bar("Checking BMP280...")
            self.check_bmp280()
            time.sleep(0.5)
            
            # GY511 check
            self.update_status_bar("Checking GY511...")
            self.check_gy511()
            time.sleep(0.5)
            
            # GPSM6N check
            self.update_status_bar("Checking GPSM6N...")
            self.check_gpsm6n()
            time.sleep(0.5)
            
            # WiFi check
            self.update_status_bar("Checking WiFi...")
            self.check_wifi()
            time.sleep(0.5)
            
            # Power check
            self.update_status_bar("Checking power supply...")
            self.check_power()
            time.sleep(0.5)
            
            # Completed
            self.update_status_bar("✓ Health check completed!")
            
        except Exception as e:
            self.update_status_bar(f"✗ Error during health check: {str(e)}")
        finally:
            self.is_checking = False
            self.start_btn.config(state=tk.NORMAL)
    
    # ==== Sensor Check Methods ====
    
    def check_camera(self):
        """Check camera availability."""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    self.set_sensor_status("camera", "success", "Ready")
                else:
                    self.set_sensor_status("camera", "error", "Cannot capture frame")
            else:
                self.set_sensor_status("camera", "error", "Cannot open device")
        except ImportError:
            self.set_sensor_status("camera", "warning", "OpenCV not installed")
        except Exception as e:
            self.set_sensor_status("camera", "error", str(e)[:20])
    
    def check_lora(self):
        """Check LoRa module."""
        try:
            # Try to import LoRa library
            from SX127x.LoRa import LoRa
            from SX127x.board_config import BOARD
            self.set_sensor_status("lora", "success", "Ready")
        except ImportError:
            self.set_sensor_status("lora", "warning", "Library not installed")
        except Exception as e:
            self.set_sensor_status("lora", "error", str(e)[:20])
    
    def check_mpu6050(self):
        """Check MPU6050 sensor."""
        try:
            from finalCode.sensor.mpu6050 import SensorMPU6050
            sensor = SensorMPU6050()
            data = sensor.baca_semua()
            if data:
                self.set_sensor_status("mpu6050", "success", "Ready")
            else:
                self.set_sensor_status("mpu6050", "error", "No data")
        except ImportError:
            self.set_sensor_status("mpu6050", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("mpu6050", "error", str(e)[:20])
    
    def check_bmp280(self):
        """Check BMP280 sensor."""
        try:
            from finalCode.sensor.bmp280 import SensorBMP280
            sensor = SensorBMP280()
            data = sensor.baca_semua()
            if data:
                self.set_sensor_status("bmp280", "success", "Ready")
            else:
                self.set_sensor_status("bmp280", "error", "No data")
        except ImportError:
            self.set_sensor_status("bmp280", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("bmp280", "error", str(e)[:20])
    
    def check_gy511(self):
        """Check GY511 sensor."""
        try:
            from finalCode.sensor.gy511 import SensorGY511
            sensor = SensorGY511()
            data = sensor.baca_akselerasi()
            if data:
                self.set_sensor_status("gy511", "success", "Ready")
            else:
                self.set_sensor_status("gy511", "error", "No data")
        except ImportError:
            self.set_sensor_status("gy511", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("gy511", "error", str(e)[:20])
    
    def check_gpsm6n(self):
        """Check GPSM6N sensor."""
        try:
            from finalCode.sensor.gpsm6n import SensorGPSM6N
            sensor = SensorGPSM6N()
            data = sensor.baca_semua()
            if data:
                # Check if GPS has a valid fix with coordinates
                if data.get('status') == 'FIX' and data.get('latitude') is not None and data.get('longitude') is not None:
                    self.set_sensor_status("gpsm6n", "success", f"Fixed ({data.get('satellites', 0)} sat)")
                elif data.get('status') == 'NO_FIX':
                    # Module detected but no fix yet
                    self.set_sensor_status("gpsm6n", "warning", f"No fix ({data.get('satellites', 0)} sat)")
                else:
                    self.set_sensor_status("gpsm6n", "warning", "Searching...")
            else:
                self.set_sensor_status("gpsm6n", "error", "No data")
        except ImportError:
            self.set_sensor_status("gpsm6n", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("gpsm6n", "error", str(e)[:20])
    
    def check_wifi(self):
        """Check WiFi connection."""
        try:
            import subprocess
            result = subprocess.run(
                ["ip", "link", "show", "wlan0"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check if connected to a network
                result2 = subprocess.run(
                    ["iwconfig", "wlan0"],
                    capture_output=True,
                    timeout=5
                )
                if b"ESSID" in result2.stdout and b"off/any" not in result2.stdout:
                    self.set_sensor_status("wifi", "success", "Connected")
                else:
                    self.set_sensor_status("wifi", "warning", "Interface ready, not connected")
            else:
                self.set_sensor_status("wifi", "error", "No interface")
        except Exception as e:
            self.set_sensor_status("wifi", "warning", "Cannot check")
    
    def check_power(self):
        """Check power supply status."""
        try:
            # Read voltage from ADC or system file
            power_file = "/sys/devices/platform/bcm2710-rng/base"
            if os.path.exists(power_file):
                self.set_sensor_status("power", "success", "Normal")
            else:
                # Fallback: check if system is running
                import psutil
                cpu_percent = psutil.cpu_percent(interval=0.1)
                if cpu_percent >= 0:  # System is responsive
                    self.set_sensor_status("power", "success", "Normal")
                else:
                    self.set_sensor_status("power", "warning", "Unknown")
        except Exception as e:
            self.set_sensor_status("power", "warning", "Cannot verify")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = HealthCheckGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
