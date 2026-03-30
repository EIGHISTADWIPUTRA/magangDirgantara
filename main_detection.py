"""
main_detection.py
Feature Matching real-time dengan 4 algoritma: AKAZE, ORB, SIFT, SURF (+ FLANN)
- Gambar target  : folder received_images/
- Sumber video   : kamera
"""

import cv2
import numpy as np
import os
import sys
import time

from modules.kamera import WebcamStream

# ─── Konfigurasi ──────────────────────────────────────────────────────────────
RECEIVED_IMAGES_DIR = 'received_images'
CAMERA_INDEX        = 0
CAMERA_WIDTH        = 640
CAMERA_HEIGHT       = 480
MIN_GOOD_MATCHES    = 10      # Ambang batas match agar dianggap "terdeteksi"
MATCH_RATIO         = 0.7     # Lowe's ratio test threshold
MAX_DRAW_MATCHES    = 30      # Batas jumlah match yang digambar
# ──────────────────────────────────────────────────────────────────────────────

# Urutan algoritma yang tersedia
ALGORITMA = ['AKAZE', 'ORB', 'SIFT', 'SURF']


def buat_detector_dan_flann(nama_algo: str):
    """
    Buat pasangan (detector, flann) sesuai algoritma.
    Binary descriptor (AKAZE, ORB) → FLANN LSH.
    Float descriptor (SIFT, SURF)  → FLANN KDTree.
    Kembalikan (None, None) jika algoritma tidak tersedia.
    """
    lsh_params    = dict(algorithm=6, table_number=6, key_size=12, multi_probe_level=1)
    kdtree_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)

    if nama_algo == 'AKAZE':
        detector = cv2.AKAZE_create()
        flann    = cv2.FlannBasedMatcher(lsh_params, search_params)

    elif nama_algo == 'ORB':
        detector = cv2.ORB_create(nfeatures=1500)
        flann    = cv2.FlannBasedMatcher(lsh_params, search_params)

    elif nama_algo == 'SIFT':
        detector = cv2.SIFT_create()
        flann    = cv2.FlannBasedMatcher(kdtree_params, search_params)

    elif nama_algo == 'SURF':
        if not hasattr(cv2, 'xfeatures2d'):
            print("    [!] SURF tidak tersedia (butuh opencv-contrib-python)")
            return None, None
        try:
            detector = cv2.xfeatures2d.SURF_create(hessianThreshold=400)
        except cv2.error:
            print("    [!] SURF tidak tersedia di instalasi OpenCV ini")
            return None, None
        flann = cv2.FlannBasedMatcher(kdtree_params, search_params)

    else:
        return None, None

    return detector, flann


def muat_gambar_target(folder: str) -> list:
    """Memuat semua gambar (jpg/png/bmp) dari folder received_images."""
    ekstensi = ('.jpg', '.jpeg', '.png', '.bmp')
    hasil = []

    if not os.path.exists(folder):
        print(f"[x] Folder '{folder}' tidak ditemukan")
        return hasil

    for nama in sorted(os.listdir(folder)):
        if nama.lower().endswith(ekstensi):
            path = os.path.join(folder, nama)
            img = cv2.imread(path)
            if img is not None:
                hasil.append({'nama': nama, 'img': img, 'path': path})
                print(f"    [V] {nama}")
            else:
                print(f"    [!] Gagal memuat: {nama}")

    return hasil


def preprocess_targets(gambar_list: list, detector) -> list:
    """Ekstrak keypoints & descriptor dari setiap gambar target."""
    targets = []
    for item in gambar_list:
        gray = cv2.cvtColor(item['img'], cv2.COLOR_BGR2GRAY)
        kp, desc = detector.detectAndCompute(gray, None)
        if desc is not None and len(kp) > 0:
            # FLANN butuh float32 untuk KDTree (SIFT/SURF)
            if desc.dtype != np.uint8:
                desc = desc.astype(np.float32)
            targets.append({
                'nama': item['nama'],
                'img' : item['img'],
                'kp'  : kp,
                'desc': desc,
            })
            print(f"    [V] {item['nama']} — {len(kp)} keypoints")
        else:
            print(f"    [!] Tidak ada keypoints di {item['nama']}, dilewati")
    return targets


def cari_match_terbaik(targets: list, flann, desc_frame) -> dict | None:
    """Kembalikan target dengan jumlah good_matches terbanyak."""
    terbaik    = None
    max_matches = 0

    for target in targets:
        try:
            raw  = flann.knnMatch(target['desc'], desc_frame, k=2)
            good = [m for pair in raw if len(pair) == 2
                    for m, n in [pair] if m.distance < MATCH_RATIO * n.distance]
            if len(good) > max_matches:
                max_matches = len(good)
                terbaik = {'target': target, 'good_matches': good, 'jumlah': len(good)}
        except Exception:
            continue

    return terbaik


def match_satu_target(target: dict, flann, desc_frame) -> dict:
    """Lakukan matching terhadap satu target tertentu."""
    try:
        raw  = flann.knnMatch(target['desc'], desc_frame, k=2)
        good = [m for pair in raw if len(pair) == 2
                for m, n in [pair] if m.distance < MATCH_RATIO * n.distance]
        return {'target': target, 'good_matches': good, 'jumlah': len(good)}
    except Exception:
        return {'target': target, 'good_matches': [], 'jumlah': 0}


def gambar_match_visualization(match_info: dict, frame, kp_frame, nama_algo: str, fps: float, mode_auto: bool) -> np.ndarray | None:
    """Buat gambar side-by-side antara target dan frame kamera dengan garis match + overlay info."""
    if match_info is None:
        return None

    target     = match_info['target']
    good       = match_info['good_matches'][:MAX_DRAW_MATCHES]
    jumlah     = match_info['jumlah']
    terdeteksi = jumlah >= MIN_GOOD_MATCHES

    try:
        viz = cv2.drawMatches(
            target['img'], target['kp'],
            frame, kp_frame,
            good, None,
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        )

        # Overlay info di visualisasi
        status = "TERDETEKSI!" if terdeteksi else f"Matches: {jumlah}"
        warna_status = (0, 255, 0) if terdeteksi else (0, 200, 255)

        # Judul + Status match
        cv2.putText(viz, f"[{nama_algo}] {target['nama']}  |  {status}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, warna_status, 2)

        # FPS (kanan atas)
        lebar = viz.shape[1]
        cv2.putText(viz, f"FPS: {int(fps)}", (lebar - 130, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        # Mode (kiri bawah)
        mode_label = "MODE: AUTO (Best Match)" if mode_auto else f"MODE: MANUAL [{target['nama']}]"
        cv2.putText(viz, mode_label,
                    (10, viz.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        return viz
    except Exception as e:
        print(f"[!] Error visualisasi matching: {e}")
        return None




# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("====================================================")
    print("=     FEATURE MATCHING REAL-TIME (MULTI ALGO)      =")
    print("=   AKAZE | ORB | SIFT | SURF  +  FLANN            =")
    print("====================================================\n")

    # 1. Muat gambar target
    print("[*] Memuat gambar dari received_images/ ...")
    gambar_list = muat_gambar_target(RECEIVED_IMAGES_DIR)
    if not gambar_list:
        print("[x] Tidak ada gambar target di received_images/. Tambahkan gambar lalu coba lagi.")
        sys.exit(1)
    print(f"    Total: {len(gambar_list)} gambar dimuat\n")

    # 2. Buat semua detector + matcher, lewati yang tidak tersedia
    algo_aktif = []
    print("[*] Inisialisasi detector + FLANN matcher ...")
    for nama in ALGORITMA:
        det, fln = buat_detector_dan_flann(nama)
        if det is not None:
            algo_aktif.append({'nama': nama, 'detector': det, 'flann': fln, 'targets': []})
            print(f"    [V] {nama} siap")
        else:
            print(f"    [-] {nama} dilewati")
    print()

    if not algo_aktif:
        print("[x] Tidak ada algoritma yang berhasil diinisialisasi.")
        sys.exit(1)

    # 3. Pilih algoritma
    print("─" * 52)
    print(" Pilih algoritma feature matching:")
    for i, algo in enumerate(algo_aktif, start=1):
        print(f"   {i}. {algo['nama']}")
    while True:
        pilihan_algo = input(f"\nMasukkan nomor algoritma [1-{len(algo_aktif)}]: ").strip()
        if pilihan_algo.isdigit() and 1 <= int(pilihan_algo) <= len(algo_aktif):
            algo_index = int(pilihan_algo) - 1
            break
        print(f"[!] Input tidak valid. Masukkan angka antara 1 dan {len(algo_aktif)}.")
    print(f"    [V] Algoritma dipilih: {algo_aktif[algo_index]['nama']}\n")

    # 4. Preprocessing target (hanya untuk algoritma yang dipilih)
    algo_dipilih = algo_aktif[algo_index]
    print(f"[*] Mengekstrak keypoints dari gambar target [{algo_dipilih['nama']}] ...")
    algo_dipilih['targets'] = preprocess_targets(gambar_list, algo_dipilih['detector'])
    if not algo_dipilih['targets']:
        print("[x] Tidak ada gambar target yang memiliki keypoints.")
        sys.exit(1)
    print(f"    Total: {len(algo_dipilih['targets'])} target valid\n")

    # 5. Pilih target
    targets_tersedia = algo_dipilih['targets']
    print("─" * 52)
    print(" Pilih gambar target:")
    print(f"   0. Semua target (mode otomatis — best match)")
    for i, t in enumerate(targets_tersedia, start=1):
        print(f"   {i}. {t['nama']}")
    while True:
        pilihan_target = input(f"\nMasukkan nomor target [0-{len(targets_tersedia)}]: ").strip()
        if pilihan_target.isdigit() and 0 <= int(pilihan_target) <= len(targets_tersedia):
            pilihan_target = int(pilihan_target)
            break
        print(f"[!] Input tidak valid. Masukkan angka antara 0 dan {len(targets_tersedia)}.")

    if pilihan_target == 0:
        mode_auto    = True
        target_index = 0
        print("    [V] Mode: otomatis (best match dari semua target)\n")
    else:
        mode_auto    = False
        target_index = pilihan_target - 1
        print(f"    [V] Target dipilih: {targets_tersedia[target_index]['nama']}\n")

    # 6. Buka kamera
    print("[*] Membuka kamera ...")
    try:
        kamera = WebcamStream(CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT)
    except Exception as e:
        print(f"[x] Gagal membuka kamera: {e}")
        sys.exit(1)

    if not kamera.siap():
        print("[x] Kamera tidak tersedia")
        sys.exit(1)
    print("    [V] Kamera siap\n")

    print("─" * 52)
    print(" Kontrol keyboard saat program berjalan:")
    print("   q  : keluar")
    print("   n  : target berikutnya")
    print("   p  : target sebelumnya")
    print("   a  : mode otomatis (best match)")
    print("─" * 52 + "\n")

    p_time = time.time()

    try:
        while True:
            terhubung, frame = kamera.get_frame()
            if not terhubung or frame is None:
                print("[x] Gagal mengambil frame dari kamera")
                break

            # Hitung FPS
            c_time = time.time()
            fps    = 1.0 / (c_time - p_time) if (c_time - p_time) > 0 else 0.0
            p_time = c_time

            algo       = algo_dipilih
            detector   = algo['detector']
            flann      = algo['flann']
            targets    = targets_tersedia
            nama_algo  = algo['nama']

            # Grayscale untuk feature matching
            gray_frame             = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            kp_frame, desc_frame   = detector.detectAndCompute(gray_frame, None)

            # Float32 untuk SIFT/SURF
            if desc_frame is not None and desc_frame.dtype != np.uint8:
                desc_frame = desc_frame.astype(np.float32)

            # ── Feature Matching ──────────────────────────────────────────
            match_info = None
            if desc_frame is not None and len(kp_frame) > 0 and targets:
                if mode_auto:
                    match_info = cari_match_terbaik(targets, flann, desc_frame)
                else:
                    aktif      = targets[target_index % len(targets)]
                    match_info = match_satu_target(aktif, flann, desc_frame)

            # ── Visualisasi dan tampilkan window ──────────────────────────
            if match_info and kp_frame:
                viz = gambar_match_visualization(match_info, frame, kp_frame, nama_algo, fps, mode_auto)
                if viz is not None:
                    cv2.imshow("Feature Matching", viz)

            # ── Kontrol keyboard ──────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("[*] Keluar...")
                break
            elif key == ord('n'):
                if targets:
                    mode_auto    = False
                    target_index = (target_index + 1) % len(targets)
                    print(f"[*] Target aktif: {targets[target_index]['nama']}")
            elif key == ord('p'):
                if targets:
                    mode_auto    = False
                    target_index = (target_index - 1) % len(targets)
                    print(f"[*] Target aktif: {targets[target_index]['nama']}")
            elif key == ord('a'):
                mode_auto = True
                print("[*] Mode otomatis: mencari best match dari semua target")

    except KeyboardInterrupt:
        print("\n[*] Program dihentikan oleh user")
    finally:
        kamera.berhenti()
        cv2.destroyAllWindows()
        print("[V] Program selesai")


if __name__ == "__main__":
    main()
