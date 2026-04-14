"""
Class Sensor GY-511 Standalone (LSM303D Version)
Alamat I2C: 0x1E
"""

import time
import math

class SensorGY511:
    
    def __init__(self, address=0x1E):
        self._sensor = None
        self._has_sensor = False
        
        try:
            # Menggunakan library lsm303d dari Pimoroni
            from lsm303d import LSM303D
            
            # Inisialisasi sensor di alamat default (0x1E)
            self._sensor = LSM303D(address)
            self._has_sensor = True
            print(f"[OK] GY-511 (LSM303D) terdeteksi di alamat {hex(address)}")
            
        except ImportError:
            print("[WARN] Library lsm303d belum di-install. Jalankan: pip install lsm303d")
        except Exception as e:
            print(f"[WARN] Gagal inisialisasi GY-511: {e}")

    def baca_akselerasi(self):
        """Membaca data akselerometer (G-force)"""
        if not self._has_sensor:
            return {"ax": 0.0, "ay": 0.0, "az": 0.0, "error": "Sensor tidak tersedia"}
        try:
            ax, ay, az = self._sensor.accelerometer()
            return {"ax": round(ax, 2), "ay": round(ay, 2), "az": round(az, 2)}
        except Exception as e:
            return {"ax": 0.0, "ay": 0.0, "az": 0.0, "error": str(e)}

    def baca_magnetometer(self):
        """Membaca data magnetometer / kompas"""
        if not self._has_sensor:
            return {"mx": 0.0, "my": 0.0, "mz": 0.0, "error": "Sensor tidak tersedia"}
        try:
            mx, my, mz = self._sensor.magnetometer()
            return {"mx": round(mx, 2), "my": round(my, 2), "mz": round(mz, 2)}
        except Exception as e:
            return {"mx": 0.0, "my": 0.0, "mz": 0.0, "error": str(e)}

    def baca_heading(self):
        """Menghitung derajat arah mata angin (Heading) berdasarkan sumbu X dan Y"""
        if not self._has_sensor:
            return 0.0
        
        mag = self.baca_magnetometer()
        if "error" in mag:
            return 0.0
            
        # Kalkulasi sudut atan2
        heading = math.atan2(mag['my'], mag['mx']) * (180 / math.pi)
        
        # Normalisasi ke 0 - 360 derajat
        if heading < 0:
            heading += 360
            
        return round(heading, 2)

    def baca_orientasi(self):
        """
        Menghitung orientasi dalam derajat (pitch, roll, heading) dengan Tilt-Compensation.
        
        Perbaikan dari versi sebelumnya:
        1. Tilt-Compensated Heading - proyeksi magnetometer ke bidang horizontal
        2. Epsilon safety untuk mencegah singularity saat az mendekati nol
        3. Heading stabil meski sensor dimiringkan (tidak hanya akurat di meja datar)
        
        - Pitch: Kemiringan depan/belakang (-90° sampai +90°)
        - Roll: Kemiringan kiri/kanan (-180° sampai +180°)
        - Heading: Arah kompas terkompensasi kemiringan (0° sampai 360°)
        
        Returns:
            dict: {'pitch': float, 'roll': float, 'heading': float}
        """
        if not self._has_sensor:
            return {"pitch": 0.0, "roll": 0.0, "heading": 0.0, "error": "Sensor tidak tersedia"}
        
        accel = self.baca_akselerasi()
        mag = self.baca_magnetometer()  # Ambil data magnetometer secara bersamaan
        
        if "error" in accel or "error" in mag:
            return {"pitch": 0.0, "roll": 0.0, "heading": 0.0, "error": "Sensor error"}
        
        ax, ay, az = accel['ax'], accel['ay'], accel['az']
        mx, my, mz = mag['mx'], mag['my'], mag['mz']
        
        # 1. Hitung Pitch dan Roll (dengan pengaman pembagian nol)
        # Menambahkan sedikit nilai epsilon untuk mencegah singularity jika az benar-benar 0
        epsilon = 0.0001
        
        pitch = math.atan2(-ax, math.sqrt(ay**2 + az**2)) 
        roll = math.atan2(ay, az if abs(az) > epsilon else epsilon) 
        
        # 2. Tilt-Compensated Heading
        # Proyeksikan pembacaan magnetometer X dan Y ke bidang horizontal 
        # menggunakan pitch dan roll (dalam radian)
        mx_horizontal = mx * math.cos(pitch) + mz * math.sin(pitch)
        
        my_horizontal = (mx * math.sin(roll) * math.sin(pitch) + 
                         my * math.cos(roll) - 
                         mz * math.sin(roll) * math.cos(pitch))
                         
        heading = math.atan2(my_horizontal, mx_horizontal)
        
        # 3. Konversi semua radian ke derajat
        pitch_deg = pitch * (180.0 / math.pi)
        roll_deg = roll * (180.0 / math.pi)
        heading_deg = heading * (180.0 / math.pi)
        
        # Normalisasi heading ke 0-360 derajat
        if heading_deg < 0:
            heading_deg += 360.0
            
        return {
            "pitch": round(pitch_deg, 2),
            "roll": round(roll_deg, 2),
            "heading": round(heading_deg, 2)
        }

    def baca_semua(self):
        """Mengembalikan semua data dalam bentuk dictionary"""
        return {
            "akselerasi": self.baca_akselerasi(),
            "magnetometer": self.baca_magnetometer(),
            "orientasi": self.baca_orientasi(),
            "heading": self.baca_heading()
        }

    def tampilkan(self):
        """Mencetak data sensor ke terminal dengan format rapi"""
        data = self.baca_semua()
        accel = data['akselerasi']
        mag = data['magnetometer']
        orientasi = data['orientasi']

        print("=== Data GY-511 ===")
        print(" [Akselerometer]")
        if "error" in accel:
            print(f"  {accel['error']}")
        else:
            print(f"  X: {accel['ax']:>6.2f} G")
            print(f"  Y: {accel['ay']:>6.2f} G")
            print(f"  Z: {accel['az']:>6.2f} G")

        print(" [Magnetometer]")
        if "error" in mag:
            print(f"  {mag['error']}")
        else:
            print(f"  X: {mag['mx']:>8.2f}")
            print(f"  Y: {mag['my']:>8.2f}")
            print(f"  Z: {mag['mz']:>8.2f}")

        print(" [Orientasi (Derajat)]")
        if "error" in orientasi:
            print(f"  {orientasi['error']}")
        else:
            print(f"  Pitch : {orientasi['pitch']:>7.2f}°")
            print(f"  Roll  : {orientasi['roll']:>7.2f}°")
            print(f"  Heading: {orientasi['heading']:>6.2f}°")
        print("-" * 20)


# === BLOK PENGUJIAN ===
if __name__ == "__main__":
    # Membuat objek sensor
    gy511 = SensorGY511()
    
    print("\nMemulai pembacaan sensor...\n")
    try:
        while True:
            gy511.tampilkan()
            time.sleep(0.5)  # Jeda 0.5 detik agar terminal tidak terlalu cepat
            
    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh pengguna.")