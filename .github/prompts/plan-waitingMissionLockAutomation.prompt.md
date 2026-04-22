## Plan: Waiting Mission Lock Automation

Tambahkan halaman baru Waiting Misi di GUI yang terpisah dari Health Check (navigasi dalam satu window), lalu orkestrasi alur misi end-to-end: menunggu target image+class dari GCS via Socket.IO, tampilkan target di panel kiri, tunggu 3 detik, jalankan YOLO + kirim sikap LoRa, validasi lock kontinu 3 detik berdasarkan class target, hentikan deteksi+sikap, kirim pesan final LoRa 3 kali, lalu kembali ke mode menunggu target.

**Steps**
1. Phase A - Navigation dan kerangka halaman GUI (bisa paralel dengan Step 3): di [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L83), tambahkan navigasi halaman Health Check <-> Waiting Misi pada area header, lalu pisahkan kontainer konten menjadi dua view agar halaman lama tetap utuh.
2. Phase A - Layout Waiting Misi (depends on 1): di [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L83), bangun layout 3 panel horizontal dari kiri ke kanan: panel target diterima (image + class), panel YOLO camera view, panel log LoRa, plus status misi (WAITING, COUNTDOWN, TRACKING, LOCKED, COMPLETE).
3. Phase B - Kontrak data target dari Socket.IO (bisa paralel dengan Step 1): di [finalCode/server/socket_server.py](finalCode/server/socket_server.py#L67) dan [finalCode/server/socket_server.py](finalCode/server/socket_server.py#L144), perluas payload agar menerima class_name bersama image payload, simpan image seperti sekarang, dan tulis metadata target terbaru (class_name, filename, saved_path, received_at) ke file state yang stabil di folder server received_images untuk dikonsumsi GUI.
4. Phase B - Runtime server dari GUI (depends on 1): di [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L370), tambahkan manajemen proses Socket.IO server (subprocess) dari GUI: start saat masuk/menjalankan Waiting Misi, monitor status hidup-mati proses, tampilkan status di panel log, dan stop bersih saat on_close.
5. Phase C - Watcher target masuk (depends on 2,3,4): di [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L388), tambah worker watcher yang memantau metadata target terbaru dari server, lalu saat target baru datang: render preview image di panel kiri, tampilkan class_name, dan set state mission target-ready.
6. Phase C - Countdown 3 detik lalu start misi aktif (depends on 5): setelah target-ready, lakukan countdown 3 detik non-blocking di GUI, lalu trigger start kamera + YOLO inference loop dan start pengiriman sikap LoRa periodik (reuse pola lora loop yang ada di [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L574)).
7. Phase D - Deteksi lock kontinu 3 detik (depends on 6): di loop YOLO baru (pola dari [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L605)), evaluasi hasil deteksi terhadap class_name target; gunakan timer monotonic kontinu (bukan hit frame mentah) untuk lock berturut-turut 3 detik; jika class hilang, reset timer lock.
8. Phase D - Terminasi misi saat lock tercapai (depends on 7): ketika lock kontinu >= 3 detik, hentikan kirim sikap LoRa, hentikan kamera/deteksi, kirim pesan final dengan format timestamp=<time>|status=<detected>|target=<class> sebanyak 3 kali via LoRa (pakai sender yang sudah aktif, memanfaatkan API kirim di [finalCode/lora/sender.py](finalCode/lora/sender.py#L76)), lalu transisi ke state complete.
9. Phase E - Reset ke mode menunggu target baru (depends on 8): setelah pengiriman final selesai, bersihkan resource misi (kamera/thread/sender sementara), update panel status, dan kembali ke state waiting tanpa keluar dari halaman Waiting Misi.
10. Phase E - Hardening lifecycle dan safety (depends on 4,6,8,9): pastikan semua update widget dari thread tetap lewat pola aman [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L388), serta on_close di [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L370) menghentikan urut semua thread + subprocess server + cleanup LoRa.

**Relevant files**
- [finalCode/health_check_gui.py](finalCode/health_check_gui.py#L39) — penambahan navigasi halaman, layout Waiting Misi 3 panel, state machine misi, watcher target, loop YOLO mission, loop LoRa mission, dan lifecycle cleanup.
- [finalCode/server/socket_server.py](finalCode/server/socket_server.py#L67) — ekstensi payload decode untuk class_name + penyimpanan metadata target terbaru.
- [finalCode/server/socket_server.py](finalCode/server/socket_server.py#L144) — update handler upload_image/upload_target agar hasil simpan image + metadata sinkron.
- [finalCode/lora/sender_sensor.py](finalCode/lora/sender_sensor.py#L258) — reuse kirim_data untuk telemetry sikap periodik selama fase tracking.
- [finalCode/lora/sender.py](finalCode/lora/sender.py#L76) — reuse kirim untuk pesan final deteksi target (3 kali).
- [finalCode/camera/stream.py](finalCode/camera/stream.py#L13) — reuse capture kamera untuk mission loop.
- [modules/detektor.py](modules/detektor.py#L26) — reuse prediksi YOLO dan pemetaan kelas untuk validasi lock class target.

**Verification**
1. Jalankan GUI dan pastikan tombol navigasi membuka halaman Waiting Misi tanpa merusak halaman Health Check lama.
2. Dari Waiting Misi, start mode menunggu dan verifikasi subprocess Socket.IO server hidup serta statusnya tampil di log.
3. Kirim payload GCS ke event upload_target berisi image dan class_name, lalu verifikasi panel kiri menampilkan image + class yang sama.
4. Verifikasi countdown 3 detik berjalan, lalu YOLO view aktif dan log sikap LoRa mulai mengalir.
5. Arahkan kamera ke objek dengan class sesuai target dan tahan hingga 3 detik kontinu; verifikasi lock timer tidak lolos bila deteksi putus di tengah.
6. Saat lock tercapai, verifikasi urutan: stop sikap -> stop kamera/deteksi -> kirim pesan final LoRa 3 kali -> status complete.
7. Verifikasi sistem kembali ke state waiting target baru otomatis setelah final message selesai.
8. Uji kasus error: class_name tidak ada, image rusak, kamera gagal dibuka, LoRa timeout; pastikan UI tetap responsif dan kembali ke state aman.
9. Tutup aplikasi saat misi berjalan; verifikasi semua thread, camera resource, LoRa resource, dan subprocess socket server berhenti bersih.

**Decisions**
- Navigasi halaman: satu window dengan perpindahan view (Health Check dan Waiting Misi).
- Sumber target: Socket.IO server di [finalCode/server/socket_server.py](finalCode/server/socket_server.py#L143).
- Runtime server: dijalankan dari GUI sebagai thread/subprocess manager.
- Definisi lock: YOLO deteksi class target secara kontinu 3 detik.
- Field payload class: class_name.
- Format pesan final LoRa: timestamp=<time>|status=<detected>|target=<class>.
- Setelah selesai: kembali ke mode menunggu target baru.

**Scope boundaries**
- In scope: alur Waiting Misi berbasis Socket.IO + GUI + YOLO + LoRa sesuai skenario user.
- Out of scope: perubahan alur HTTP upload di [finalCode/server/wifi_server.py](finalCode/server/wifi_server.py), perubahan protokol Bluetooth di [finalCode/server/bluetooth_server.py](finalCode/server/bluetooth_server.py), dan penambahan ORB-based lock logic.