# Panduan Menjalankan Project MAGANG

Dokumen ini menjelaskan cara menyiapkan environment dan menjalankan komponen utama project.

## 1. Persiapan cepat

Jalankan dari root repo:

```bash
bash scripts/setup_env.sh
source .venv/bin/activate
```

Catatan:
- Tambahkan flag `--no-hw` jika hanya butuh fitur non-hardware.
- Tambahkan flag `--no-apt` jika tidak ingin install paket sistem.

## 2. Entry point utama (root)

Dari root repo:

```bash
# YOLO detection (NCNN model)
python main.py

# Feature matching multi-algoritma (AKAZE, ORB, SIFT, SURF)
python main_detection.py

# Target lock pipeline (optimized for Raspberry Pi)
python target_lock.py
```

## 3. Entry point finalCode (CLI)

Semua perintah berikut dijalankan dari root repo:

```bash
# ORB detection
python -m finalCode.main detect

# WiFi HTTP image server (Flask)
python -m finalCode.main server wifi

# Bluetooth image receiver (SPP)
python -m finalCode.main server bt

# LoRa basic sender
python -m finalCode.main lora send

# LoRa sender dengan data sensor
python -m finalCode.main lora sensor --sensor mpu6050

# LoRa ping-pong test
python -m finalCode.main lora ping

# Health check CLI (semua sensor)
python -m finalCode.main health
```

GUI health check:

```bash
python finalCode/health_check_gui.py
```

Socket.IO image server:

```bash
python -m finalCode.server.socket_server
```

## 4. Folder data dan model

- Folder gambar target untuk feature matching: [received_images/](received_images/).
- File model NCNN dan YOLO ada di [finalCode/models/](finalCode/models/) dan [models/](models/).
- Jalankan perintah dari root repo supaya path relatif seperti [received_images/](received_images/) konsisten.

## 5. Catatan path absolut

Beberapa file memakai path absolut ke model. Jika repo berada di lokasi berbeda,
ubah path berikut:

- [main.py](main.py) (path model YOLO NCNN)
- [finalCode/health_check_gui.py](finalCode/health_check_gui.py) (YOLO_MODEL_PATH dan folder misi)

## 6. Catatan hardware

- LoRa membutuhkan Raspberry Pi dengan SPI aktif, modul SX127x, `RPi.GPIO`, dan `spidev`.
- Sensor BMP280/MPU6050/GY511 membutuhkan I2C aktif dan library Adafruit.
- Jika GPS tidak terpasang, gunakan health check per-sensor agar tidak gagal:

```bash
python -m finalCode.sensor.health_check bmp280
python -m finalCode.sensor.health_check mpu6050
python -m finalCode.sensor.health_check gy511
python -m finalCode.sensor.health_check camera
python -m finalCode.sensor.health_check lora
```

## 7. Referensi autostart GUI

Lihat panduan detail di [finalCode/SETUP_GUI_HEALTH_CHECK.md](finalCode/SETUP_GUI_HEALTH_CHECK.md).
