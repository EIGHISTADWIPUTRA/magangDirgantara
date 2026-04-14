"""
System Health Check Module

Provides the HealthChecker class for verifying sensor and module health:
- BMP280 (Temperature, Pressure, Altitude)
- MPU-6050 (Accelerometer, Gyroscope)
- GY-511 (Accelerometer, Magnetometer, Compass)
- GPS M6N (Latitude, Longitude, Satellite lock)
- Camera
- LoRa SX127x

All imports are done dynamically inside methods to prevent crashes
when libraries are not installed.

Usage:
    from sensor.health_check import HealthChecker
    
    checker = HealthChecker()
    all_healthy = checker.run_all_checks()
    results = checker.get_results()

CLI Usage:
    python health_check.py          # Check all sensors
    python health_check.py bmp280   # Check only BMP280
    python health_check.py mpu6050  # Check only MPU-6050
    python health_check.py gy511    # Check only GY-511
    python health_check.py gpsm6n   # Check only GPS M6N
    python health_check.py camera   # Check only camera
    python health_check.py lora     # Check only LoRa
"""

import sys
import time


class HealthChecker:
    """
    System health checker for sensors and modules.
    
    Checks the following hardware:
    - BMP280 (Pressure, Temperature, Altitude)
    - MPU-6050 (Accelerometer, Gyroscope)
    - GY-511 (Accelerometer, Magnetometer, Compass)
    - GPS M6N (Latitude, Longitude, Satellite lock)
    - Camera
    - LoRa SX127x
    
    Attributes:
        results: Dictionary containing check results for each sensor
    """
    
    def __init__(self):
        """Initialize HealthChecker with empty results."""
        self.results = {}
    
    def check_bmp280(self):
        """
        Check BMP280 sensor health.
        
        Returns:
            bool: True if sensor is healthy and readable
        """
        print("\n[1/6] Memeriksa BMP280...", end=" ")
        try:
            from finalCode.sensor.bmp280 import SensorBMP280
            sensor = SensorBMP280()
            data = sensor.baca_semua()
            
            self.results['bmp280'] = {
                'status': 'SEHAT',
                'suhu': data['suhu'],
                'tekanan': data['tekanan'],
                'ketinggian': data['ketinggian']
            }
            print("✓ SEHAT")
            print(f"    - Suhu: {data['suhu']} °C")
            print(f"    - Tekanan: {data['tekanan']} hPa")
            print(f"    - Ketinggian: {data['ketinggian']} m")
            return True
        except Exception as e:
            self.results['bmp280'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
    
    def check_mpu6050(self):
        """
        Check MPU-6050 sensor health.
        
        Returns:
            bool: True if sensor is healthy and readable
        """
        print("\n[2/6] Memeriksa MPU-6050...", end=" ")
        try:
            from finalCode.sensor.mpu6050 import SensorMPU6050
            sensor = SensorMPU6050()
            data = sensor.baca_semua()
            
            accel = data['akselerasi']
            gyro = data['gyroscope']
            temp = data['suhu']
            
            self.results['mpu6050'] = {
                'status': 'SEHAT',
                'akselerasi': accel,
                'gyroscope': gyro,
                'suhu': temp
            }
            print("✓ SEHAT")
            print(f"    - Akselerasi: X={accel['ax']:.2f}, Y={accel['ay']:.2f}, Z={accel['az']:.2f} m/s²")
            print(f"    - Gyroscope: X={gyro['gx']:.2f}, Y={gyro['gy']:.2f}, Z={gyro['gz']:.2f} rad/s")
            print(f"    - Suhu: {temp:.2f} °C")
            return True
        except Exception as e:
            self.results['mpu6050'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
    
    def check_gy511(self):
        """
        Check GY-511 sensor health.
        
        Returns:
            bool: True if sensor is healthy and readable
        """
        print("\n[3/6] Memeriksa GY-511...", end=" ")
        try:
            from finalCode.sensor.gy511 import SensorGY511
            sensor = SensorGY511()
            
            # Jika sensor gagal inisialisasi dari awal
            if getattr(sensor, '_has_sensor', False) is False:
                self.results['gy511'] = {'status': 'TIDAK TERBACA', 'message': 'Sensor tidak terdeteksi di I2C'}
                print("✗ TIDAK TERBACA - Sensor tidak terdeteksi di bus I2C")
                return False

            data = sensor.baca_semua()
            accel = data['akselerasi']
            mag = data['magnetometer']
            heading = data['heading']
            
            # Validasi tambahan: Cek apakah ada kata 'error' dari pembacaan
            if "error" in accel or "error" in mag:
                pesan_error = accel.get('error', mag.get('error', 'Error tidak diketahui'))
                self.results['gy511'] = {'status': 'TIDAK TERBACA', 'message': pesan_error}
                print(f"✗ TIDAK TERBACA - {pesan_error}")
                return False
            
            self.results['gy511'] = {
                'status': 'SEHAT',
                'akselerasi': accel,
                'magnetometer': mag,
                'heading': heading
            }
            print("✓ SEHAT")
            print(f"    - Akselerasi: X={accel['ax']:.2f}, Y={accel['ay']:.2f}, Z={accel['az']:.2f} G")
            print(f"    - Magnetometer: X={mag['mx']:.2f}, Y={mag['my']:.2f}, Z={mag['mz']:.2f}")
            print(f"    - Heading: {heading:.2f}°")
            return True
            
        except Exception as e:
            self.results['gy511'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False

    def check_gpsm6n(self, port='/dev/serial0', baudrate=9600):
        """
        Check GPS M6N sensor health.

        Args:
            port: Serial device path for GPS module
            baudrate: Serial baudrate

        Returns:
            bool: True if GPS is readable and has valid coordinates/fix
        """
        print("\n[4/6] Memeriksa GPS M6N...", end=" ")
        gps = None
        try:
            from finalCode.sensor.gpsm6n import SensorGPSM6N

            gps = SensorGPSM6N(port=port, baudrate=baudrate)
            data = gps.baca_semua()

            has_coordinates = data.get('latitude') is not None and data.get('longitude') is not None
            status = data.get('status', 'NO_FIX')

            if has_coordinates:
                self.results['gpsm6n'] = {
                    'status': 'SEHAT',
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'altitude': data.get('altitude'),
                    'satellites': data.get('satellites', 0),
                    'fix_status': status,
                    'source': data.get('source'),
                    'port': data.get('port', port)
                }
                print("✓ SEHAT")
                print(f"    - Latitude: {data.get('latitude')}")
                print(f"    - Longitude: {data.get('longitude')}")
                print(f"    - Satellites: {data.get('satellites', 0)}")
                print(f"    - Fix: {status}")
                return True

            self.results['gpsm6n'] = {
                'status': 'TIDAK TERBACA',
                'message': 'Belum mendapat koordinat GPS (no fix)',
                'fix_status': status,
                'satellites': data.get('satellites', 0),
                'port': data.get('port', port)
            }
            print("✗ TIDAK TERBACA - Belum mendapat koordinat GPS (no fix)")
            return False

        except Exception as e:
            self.results['gpsm6n'] = {'status': 'TIDAK TERBACA', 'message': str(e), 'port': port}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
        finally:
            if gps is not None:
                try:
                    gps.close()
                except Exception:
                    pass

    def check_camera(self, camera_index=0):
        """
        Check camera health.
        
        Args:
            camera_index: Camera device index (default: 0)
            
        Returns:
            bool: True if camera is accessible and can capture frames
        """
        print("\n[5/6] Memeriksa Kamera...", end=" ")
        try:
            from finalCode.camera.stream import WebcamStream
            
            camera = WebcamStream(source=camera_index)
            
            if not camera.siap():
                self.results['camera'] = {'status': 'TIDAK TERBACA', 'message': 'Kamera tidak dapat dibuka'}
                print("✗ TIDAK TERBACA - Kamera tidak dapat dibuka")
                camera.berhenti()
                return False
            
            # Try to capture a frame
            ret, frame = camera.get_frame()
            camera.berhenti()
            
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
        """
        Check LoRa SX127x module health.
        
        Returns:
            bool: True if LoRa module is accessible and has valid version
        """
        print("\n[6/6] Memeriksa LoRa...", end=" ")
        try:
            from finalCode.lora.sender import check_health as lora_check_health
            result = lora_check_health()
            
            self.results['lora'] = result
            
            if result['status'] == 'SEHAT':
                print("✓ SEHAT")
                print(f"    - Version: {result['version']}")
                print(f"    - Chip: {result['chip']}")
                return True
            elif result['status'] == 'WARNING':
                print(f"⚠ WARNING - {result.get('message', 'Unknown')}")
                return False
            else:
                print(f"✗ TIDAK TERBACA - {result.get('message', 'Unknown')}")
                return False
        except Exception as e:
            self.results['lora'] = {'status': 'TIDAK TERBACA', 'message': str(e)}
            print(f"✗ TIDAK TERBACA - {e}")
            return False
    
    def run_all_checks(self):
        """
        Run all health checks.
        
        Returns:
            bool: True if all sensors are healthy
        """
        print("=" * 50)
        print("    PEMERIKSAAN KESEHATAN SISTEM")
        print("=" * 50)
        print(f"Waktu: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all checks
        bmp_ok = self.check_bmp280()
        mpu_ok = self.check_mpu6050()
        gy511_ok = self.check_gy511()
        gps_ok = self.check_gpsm6n()
        cam_ok = self.check_camera()
        lora_ok = self.check_lora()
        
        # Display summary
        self.print_summary()
        
        # Return True if all healthy
        return all([bmp_ok, mpu_ok, gy511_ok, gps_ok, cam_ok, lora_ok])
    
    def print_summary(self):
        """Display summary of check results."""
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
        total_sensors = 6
        
        sensors = [
            ('BMP280', 'bmp280'),
            ('MPU-6050', 'mpu6050'),
            ('GY-511', 'gy511'),
            ('GPS M6N', 'gpsm6n'),
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
        """
        Get check results.
        
        Returns:
            dict: Dictionary containing results for all checked sensors
        """
        return self.results
    
    def get_status(self, sensor_name):
        """
        Get status for a specific sensor.
        
        Args:
            sensor_name: Name of sensor ('bmp280', 'mpu6050', 'gy511', 'gpsm6n', 'camera', 'lora')
            
        Returns:
            dict: Sensor status dictionary, or None if not checked
        """
        if sensor_name in self.results:
            return self.results[sensor_name]
        return None


def check_single_sensor(sensor_name):
    """
    Check a single sensor by name.
    
    Args:
        sensor_name: Name of sensor to check
            Valid names: bmp280, bmp, mpu6050, mpu, gy511, gy, gpsm6n, gps, m6n, camera, cam, kamera, lora
    """
    checker = HealthChecker()
    
    sensor_checks = {
        'bmp280': checker.check_bmp280,
        'bmp': checker.check_bmp280,
        'mpu6050': checker.check_mpu6050,
        'mpu': checker.check_mpu6050,
        'gy511': checker.check_gy511,
        'gy': checker.check_gy511,
        'gpsm6n': checker.check_gpsm6n,
        'gps': checker.check_gpsm6n,
        'm6n': checker.check_gpsm6n,
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
        # Check specific sensor
        sensor = sys.argv[1]
        check_single_sensor(sensor)
    else:
        # Check all sensors
        checker = HealthChecker()
        all_healthy = checker.run_all_checks()
        
        # Exit code for scripting
        sys.exit(0 if all_healthy else 1)
