# 📋 Panduan Setup Health Check GUI di Raspberry Pi

Program GUI health check telah dibuat. Dokumen ini menjelaskan cara setup dan autostart.

---

## 📦 Persiapan Awal

### 1. **Install Library yang Diperlukan**

Jalankan perintah berikut di terminal Raspberry Pi:

```bash
# Update package manager
sudo apt update && sudo apt upgrade -y

# Install Python3 dan dependency
sudo apt install -y python3-pip python3-tk python3-dev

# Install library yang diperlukan
pip3 install opencv-python
pip3 install RPi.GPIO
pip3 install SX127x
pip3 install psutil
pip3 install ultralytics

# Untuk sensor WiFi check (jika belum ada)
sudo apt install -y wireless-tools

# Untuk GPS (jika menggunakan GPSM6N)
pip3 install pynmea2 pyserial
```

### 2. **Verifikasi Instalasi**

```bash
# Cek Python version (harus 3.6+)
python3 --version

# Cek tkinter
python3 -m tkinter

# Jika window tkinter muncul → ✓ OK

# Cek library lainnya
python3 -c "import cv2; print('OpenCV OK')"
python3 -c "import RPi.GPIO; print('GPIO OK')"
```

---

## ▶️ Menjalankan Program

### **Cara 1: Langsung dari Terminal**

```bash
# Jika menggunakan venv, aktifkan terlebih dahulu
source /path/to/venv/bin/activate

# Navigate ke project folder
cd ~/Documents/MAGANG/finalCode

# Run program
python3 health_check_gui.py

# Atau menggunakan module runner
python3 -m finalCode.health_check_gui
```

> Panel YOLO di GUI menggunakan model di path:
> `/home/eighista/Documents/MAGANG/finalCode/models/yolo.pt`
>
> Class yang diproses hanya: `1, 2, 3`.

### **Cara 2: Membuat Desktop Shortcut**

Buat file `.desktop` di desktop:

```bash
nano ~/Desktop/HealthCheck.desktop
```

Isi dengan:

```ini
[Desktop Entry]
Type=Application
Name=Health Check
Comment=System Health Check GUI
Exec=python3 /home/pi/Documents/MAGANG/finalCode/health_check_gui.py
Icon=system-run
Terminal=false
Categories=Utility;
```

Buat executable:

```bash
chmod +x ~/Desktop/HealthCheck.desktop
```

---

## 🚀 Setup Autostart di Boot

### **Opsi 1: Menggunakan systemd (RECOMMENDED)**

**Langkah 1:** Buat service file

```bash
sudo nano /etc/systemd/system/health-check-gui.service
```

**Langkah 2:** Copy isi berikut (sesuaikan `User`, path venv, dan path project):

```ini
[Unit]
Description=Health Check GUI
After=graphical.target
Wants=graphical.target

[Service]
Type=simple
User=eighista
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/eighista/.Xauthority"
Environment="PYTHONPATH=/home/eighista/Documents/MAGANG"
ExecStart=/home/eighista/Documents/MAGANG/rudal/bin/python3 /home/eighista/Documents/MAGANG/finalCode/health_check_gui.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=graphical.target
```

> 💡 **PENTING:**
> - `User=eighista` → Ganti dengan username Anda (harus cocok dengan venv owner)
> - `/home/eighista/Documents/MAGANG/rudal` → Path ke venv Anda (BUKAN global python `/usr/bin/python3`)
> - `PYTHONPATH=/home/eighista/Documents/MAGANG` → Path root project (agar module import bekerja)
> - `/home/eighista/Documents/MAGANG/finalCode` → Path ke project folder Anda

**Langkah 3:** Enable service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable autostart
sudo systemctl enable health-check-gui.service

# Start service
sudo systemctl start health-check-gui.service

# Check status
sudo systemctl status health-check-gui.service
```

**Langkah 4:** Verifikasi

Reboot dan lihat apakah GUI muncul:

```bash
sudo reboot
```

---

### **Opsi 2: Menggunakan crontab (Alternatif Simpel)**

```bash
# Edit crontab
sudo crontab -e

# Tambahkan baris ini di akhir:
@reboot sleep 10 && export DISPLAY=:0 && /usr/bin/python3 /home/pi/Documents/MAGANG/finalCode/health_check_gui.py &
```

---

### **Opsi 3: Menggunakan /etc/rc.local (Legacy)**

```bash
# Edit rc.local
sudo nano /etc/rc.local
```

Tambahkan sebelum `exit 0`:

```bash
# Start Health Check GUI
su - pi -c "export DISPLAY=:0 && python3 /home/pi/Documents/MAGANG/finalCode/health_check_gui.py &" &
```

---

## 🔧 Troubleshooting

### **GUI Tidak Muncul saat Boot**

1. **Check service status:**
   ```bash
   sudo systemctl status health-check-gui.service
   sudo journalctl -u health-check-gui.service -n 20
   ```

2. **Check DISPLAY variable:**
   ```bash
   echo $DISPLAY
   # Harus output :0 atau :1
   ```

3. **Test manual dengan DISPLAY:**
   ```bash
   DISPLAY=:0 python3 health_check_gui.py
   ```

### **Error: "No module named 'tkinter'"**

```bash
sudo apt install -y python3-tk
```

### **Error: "Cannot connect to X server"**

GUI memerlukan display server. Pastikan:
- Desktop environment sudah running (LXDE/XFCE)
- SSH tidak digunakan (atau gunakan X11 forwarding)

---

## 📊 Fitur Program

| Fitur | Deskripsi |
|-------|-----------|
| **Real-time Check** | Cek semua sensor one-by-one |
| **Visual Status** | Green (OK), Yellow (Warning), Red (Error) |
| **Background Thread** | Tidak freeze UI saat checking |
| **Start/Reset/Exit** | Button kontrol penuh |
| **Status Bar** | Info real-time progress |

---

## 🎨 Struktur GUI

```
┌─────────────────────────────────────┐
│    🔧 System Health Check           │  ← Header
├─────────────────────────────────────┤
│ Sensor Status:                      │
│                                     │
│ 📷 Camera             ● OK          │
│ 📡 LoRa Module        ● OK          │
│ 🧭 MPU6050            ● OK          │
│ 🌡️  BMP280             ● ERROR       │
│ 💡 GY511              ● WARNING     │
│ 🗺️  GPSM6N             ● PENDING     │
│ 📶 WiFi Connection    ● OK          │
│ 🔋 Power Supply       ● OK          │
│                                     │
├─────────────────────────────────────┤
│ [▶ Start Check] [🔄 Reset] [✕ Exit]│
├─────────────────────────────────────┤
│ Ready                               │  ← Status bar
└─────────────────────────────────────┘
```

---

## 📝 Modifikasi Lanjutan (Optional)

### **Tambah Sensor Custom**

Edit `health_check_gui.py` di method `build_ui()`:

```python
self.sensors_list = [
    ('📷 Camera', 'camera'),
    ('🆕 Custom Sensor', 'custom_sensor'),  # ← Tambah ini
    # ... sensor lainnya
]
```

Kemudian tambah method check:

```python
def check_custom_sensor(self):
    """Check custom sensor."""
    try:
        # Your custom check logic here
        self.set_sensor_status("custom_sensor", "success", "Ready")
    except Exception as e:
        self.set_sensor_status("custom_sensor", "error", str(e)[:20])
```

Dan panggil di `perform_health_check()`:

```python
self.check_custom_sensor()
```

---

## ✅ Checklist Setup

- [ ] Install semua library (`pip3 install ...`)
- [ ] Test jalankan program di terminal
- [ ] Pilih method autostart (Opsi 1/2/3)
- [ ] Setup service/crontab/rc.local
- [ ] Reboot dan verifikasi GUI muncul
- [ ] Test semua sensor dengan button "Start Check"

---

## 📞 Notes

- Program menggunakan `threading` agar UI tidak freeze
- Setiap sensor check berjalan secara sequential untuk akurasi
- Total waktu check ≈ 5-10 detik tergantung sensor
- Log dapat dilihat via `journalctl` untuk debugging

---

**Generated:** April 2026
