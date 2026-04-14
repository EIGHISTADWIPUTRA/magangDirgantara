import sys
import time

class HealthChecker:
    """
    Kelas untuk memeriksa kesehatan semua sensor dan modul:
    - BMP280 (Tekanan, Suhu, Ketinggian)
    - MPU-6050 (Akselerometer, Gyroscope)
    - Kamera
    - LoRa SX127x
    """
    
    def __init__(self):
        self.results = {}
    
    def check_bmp280(self):
        """Memeriksa kesehatan sensor BMP280"""
        print("\n[1/4] Memeriksa BMP280...", end=" ")
        try:
            import board
            import busio
            import adafruit_bmp280
            
            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)
            
            # Coba baca data
            temp = sensor.temperature
            pressure = sensor.pressure
            altitude = sensor.altitude
            
            if temp is not None and pressure is not None:
                self.results['bmp280'] = {
                    'status': 'SEHAT',
                    'suhu': round(temp, 2),
                    'tekanan': round(pressure, 2),
                    'ketinggian': round(altitude, 2)
                }
                print("✓ SEHAT")
                print(f"    - Suhu: {temp:.2f} °C")
                print(f"    - Tekanan: {pressure:.2f} hPa")
                print(f"    - Ketinggian: {altitude:.2f} m")
                return True
            else:
                self.results['bmp280'] = {'status': 'ERROR', 'message': 'Data tidak valid'}
                print("✗ ERROR - Data tidak valid")
                return False
                
        except Exception as e:
            self.results['bmp280'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
    
    def check_mpu6050(self):
        """Memeriksa kesehatan sensor MPU-6050"""
        print("\n[2/4] Memeriksa MPU-6050...", end=" ")
        try:
            import board
            import busio
            import adafruit_mpu6050
            
            i2c = busio.I2C(board.SCL, board.SDA)
            sensor = adafruit_mpu6050.MPU6050(i2c, address=0x68)
            
            # Coba baca data
            accel = sensor.acceleration
            gyro = sensor.gyro
            temp = sensor.temperature
            
            if accel is not None and gyro is not None:
                self.results['mpu6050'] = {
                    'status': 'SEHAT',
                    'akselerasi': {
                        'x': round(accel[0], 2),
                        'y': round(accel[1], 2),
                        'z': round(accel[2], 2)
                    },
                    'gyroscope': {
                        'x': round(gyro[0], 2),
                        'y': round(gyro[1], 2),
                        'z': round(gyro[2], 2)
                    },
                    'suhu': round(temp, 2)
                }
                print("✓ SEHAT")
                print(f"    - Akselerasi: X={accel[0]:.2f}, Y={accel[1]:.2f}, Z={accel[2]:.2f} m/s²")
                print(f"    - Gyroscope: X={gyro[0]:.2f}, Y={gyro[1]:.2f}, Z={gyro[2]:.2f} rad/s")
                print(f"    - Suhu: {temp:.2f} °C")
                return True
            else:
                self.results['mpu6050'] = {'status': 'ERROR', 'message': 'Data tidak valid'}
                print("✗ ERROR - Data tidak valid")
                return False
                
        except Exception as e:
            self.results['mpu6050'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
    
    def check_camera(self, camera_index=0):
        """Memeriksa kesehatan kamera"""
        print("\n[3/4] Memeriksa Kamera...", end=" ")
        try:
            import cv2
            
            cap = cv2.VideoCapture(camera_index)
            
            if not cap.isOpened():
                self.results['camera'] = {'status': 'TIDAK TERBACA', 'message': 'Kamera tidak dapat dibuka'}
                print("✗ TIDAK TERBACA - Kamera tidak dapat dibuka")
                return False
            
            # Coba ambil frame
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                height, width = frame.shape[:2]
                self.results['camera'] = {
                    'status': 'SEHAT',
                    'resolusi': f"{width}x{height}",
                    'index': camera_index
                }
                print("✓ SEHAT")
                print(f"    - Resolusi: {width}x{height}")
                print(f"    - Index: {camera_index}")
                return True
            else:
                self.results['camera'] = {'status': 'ERROR', 'message': 'Gagal mengambil frame'}
                print("✗ ERROR - Gagal mengambil frame")
                return False
                
        except Exception as e:
            self.results['camera'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
    
    def check_lora(self):
        """Memeriksa kesehatan modul LoRa SX127x"""
        print("\n[4/4] Memeriksa LoRa...", end=" ")
        try:
            import RPi.GPIO as GPIO
            from SX127x.LoRa import LoRa, MODE
            from SX127x.board_config import BOARD
            
            GPIO.setwarnings(False)
            GPIO.cleanup()
            BOARD.setup()
            
            class LoRaCheck(LoRa):
                def __init__(self, verbose=False):
                    super(LoRaCheck, self).__init__(verbose)
            
            lora = LoRaCheck(verbose=False)
            version = lora.get_version()
            
            # Set ke mode sleep sebelum cleanup
            try:
                lora.set_mode(MODE.SLEEP)
            except:
                pass
            
            BOARD.teardown()
            
            # Version 0x12 (18) adalah versi valid SX127x
            if version == 18:
                self.results['lora'] = {
                    'status': 'SEHAT',
                    'version': f"0x{version:02X}",
                    'chip': 'SX127x'
                }
                print("✓ SEHAT")
                print(f"    - Version: 0x{version:02X}")
                print(f"    - Chip: SX127x")
                return True
            else:
                self.results['lora'] = {
                    'status': 'WARNING',
                    'version': f"0x{version:02X}",
                    'message': 'Version tidak dikenal'
                }
                print(f"⚠ WARNING - Version tidak dikenal (0x{version:02X})")
                return False
                
        except Exception as e:
            self.results['lora'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            # Cleanup GPIO jika terjadi error
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup()
            except:
                pass
            return False
    
    def run_all_checks(self):
        """Menjalankan semua pemeriksaan kesehatan"""
        print("=" * 50)
        print("    PEMERIKSAAN KESEHATAN SISTEM")
        print("=" * 50)
        print(f"Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Jalankan semua pemeriksaan
        bmp_ok = self.check_bmp280()
        mpu_ok = self.check_mpu6050()
        cam_ok = self.check_camera()
        lora_ok = self.check_lora()
        
        # Tampilkan ringkasan
        self.print_summary()
        
        # Return True jika semua sehat
        return all([bmp_ok, mpu_ok, cam_ok, lora_ok])
    
    def print_summary(self):
        """Menampilkan ringkasan hasil pemeriksaan"""
        print("\n" + "=" * 50)
        print("    RINGKASAN HASIL")
        print("=" * 50)
        
        status_icons = {
            'SEHAT': '✓',
            'WARNING': '⚠',
            'ERROR': '✗',
            'TIDAK TERBACA': '✗'
        }
        
        total_ok = 0
        total_sensors = 4
        
        sensors = [
            ('BMP280', 'bmp280'),
            ('MPU-6050', 'mpu6050'),
            ('Camera', 'camera'),
            ('LoRa', 'lora')
        ]
        
        for name, key in sensors:
            if key in self.results:
                status = self.results[key]['status']
                icon = status_icons.get(status, '?')
                print(f"  {icon} {name}: {status}")
                if status == 'SEHAT':
                    total_ok += 1
            else:
                print(f"  ? {name}: TIDAK DIPERIKSA")
        
        print("-" * 50)
        print(f"  Total: {total_ok}/{total_sensors} sensor berfungsi normal")
        
        if total_ok == total_sensors:
            print("\n  ✓ SISTEM SEHAT - Semua sensor berfungsi normal")
        elif total_ok > 0:
            print("\n  ⚠ SISTEM PARTIAL - Beberapa sensor bermasalah")
        else:
            print("\n  ✗ SISTEM ERROR - Semua sensor bermasalah")
        
        print("=" * 50)
    
    def get_results(self):
        """Mengembalikan hasil pemeriksaan dalam format dictionary"""
        return self.results
    
    def get_status(self, sensor_name):
        """Mengembalikan status sensor tertentu"""
        if sensor_name in self.results:
            return self.results[sensor_name]
        return None


def check_single_sensor(sensor_name):
    """Memeriksa satu sensor tertentu"""
    checker = HealthChecker()
    
    sensor_checks = {
        'bmp280': checker.check_bmp280,
        'bmp': checker.check_bmp280,
        'mpu6050': checker.check_mpu6050,
        'mpu': checker.check_mpu6050,
        'camera': checker.check_camera,
        'cam': checker.check_camera,
        'kamera': checker.check_camera,
        'lora': checker.check_lora
    }
    
    sensor_name = sensor_name.lower()
    if sensor_name in sensor_checks:
        print("=" * 50)
        print(f"    PEMERIKSAAN: {sensor_name.upper()}")
        print("=" * 50)
        sensor_checks[sensor_name]()
        print("=" * 50)
    else:
        print(f"[ERROR] Sensor tidak dikenal: {sensor_name}")
        print(f"Pilihan: {', '.join(sensor_checks.keys())}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Periksa sensor tertentu
        sensor = sys.argv[1]
        check_single_sensor(sensor)
    else:
        # Periksa semua sensor
        checker = HealthChecker()
        all_healthy = checker.run_all_checks()
        
        # Exit code untuk scripting
        sys.exit(0 if all_healthy else 1)
