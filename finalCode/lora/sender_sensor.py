"""
LoRa Sensor Data Sender.

Generic LoRa sender that can transmit data from multiple sensors:
- BMP280 (temperature, pressure, altitude)
- MPU6050 (acceleration, gyroscope)
- GY511 (pitch, roll, heading in degrees)
- GPSM6N (latitude, longitude, satellite lock)
- SIKAP mode (timestamp, MPU pitch/roll, GY511 yaw, BMP pressure/altitude)
- SIKAP_GPS mode (SIKAP + GPS position/status)
- All sensors simultaneously

Usage:
    python -m finalCode.lora.sender_sensor --sensor bmp280
    python -m finalCode.lora.sender_sensor --sensor mpu6050
    python -m finalCode.lora.sender_sensor --sensor gy511
    python -m finalCode.lora.sender_sensor --sensor gpsm6n
    python -m finalCode.lora.sender_sensor --sensor sikap
    python -m finalCode.lora.sender_sensor --sensor sikap_gps
    python -m finalCode.lora.sender_sensor --sensor all
"""

import sys
import time
import argparse

# Lazy imports for sensors - done at init time for better error handling
SensorBMP280 = None
SensorMPU6050 = None
SensorGY511 = None
SensorGPSM6N = None


def _import_bmp280():
    """Import BMP280 sensor module with error handling."""
    global SensorBMP280
    if SensorBMP280 is None:
        try:
            from finalCode.sensor.bmp280 import SensorBMP280 as _SensorBMP280
            SensorBMP280 = _SensorBMP280
        except ImportError as e:
            raise ImportError(
                f"Failed to import BMP280 sensor. "
                f"Install required packages: adafruit-circuitpython-bmp280. "
                f"Error: {e}"
            )
    return SensorBMP280


def _import_mpu6050():
    """Import MPU6050 sensor module with error handling."""
    global SensorMPU6050
    if SensorMPU6050 is None:
        try:
            from finalCode.sensor.mpu6050 import SensorMPU6050 as _SensorMPU6050
            SensorMPU6050 = _SensorMPU6050
        except ImportError as e:
            raise ImportError(
                f"Failed to import MPU6050 sensor. "
                f"Install required packages: adafruit-circuitpython-mpu6050. "
                f"Error: {e}"
            )
    return SensorMPU6050


def _import_gy511():
    """Import GY-511 sensor module with error handling."""
    global SensorGY511
    if SensorGY511 is None:
        try:
            from finalCode.sensor.gy511 import SensorGY511 as _SensorGY511
            SensorGY511 = _SensorGY511
        except ImportError as e:
            raise ImportError(
                f"Failed to import GY-511 sensor. "
                f"Install required packages: pip install lsm303d. "
                f"Error: {e}"
            )
    return SensorGY511


def _import_gpsm6n():
    """Import GPSM6N sensor module with error handling."""
    global SensorGPSM6N
    if SensorGPSM6N is None:
        try:
            from finalCode.sensor.gpsm6n import SensorGPSM6N as _SensorGPSM6N
            SensorGPSM6N = _SensorGPSM6N
        except ImportError as e:
            raise ImportError(
                f"Failed to import GPSM6N sensor. "
                f"Install required packages: pyserial. "
                f"Error: {e}"
            )
    return SensorGPSM6N


# Import LoRa components
from finalCode.lora.sender import LoRaSender, setup_gpio, teardown_gpio


class LoRaSensorSender:
    """
    Generic LoRa sender for sensor data.
    
    Can read from BMP280, MPU6050, GY511, GPSM6N, sikap mode, sikap_gps mode,
    or all and transmit via LoRa.
    
    Attributes:
        sensors (str): Which sensors to use - 'bmp280', 'mpu6050', 'gy511', 'gpsm6n',
            'sikap', 'sikap_gps', or 'all'
        verbose (bool): Enable verbose LoRa output
        bmp (SensorBMP280): BMP280 sensor instance (if enabled)
        mpu (SensorMPU6050): MPU6050 sensor instance (if enabled)
        gy511 (SensorGY511): GY511 sensor instance (if enabled)
        lora (LoRaSender): LoRa sender instance
    """
    
    VALID_SENSORS = ('bmp280', 'mpu6050', 'gy511', 'gpsm6n', 'sikap', 'sikap_gps', 'all')
    
    def __init__(self, sensors='all', verbose=False, read_gps_hardware=True):
        """
        Initialize the LoRa sensor sender.
        
        Args:
            sensors: Which sensors to use - 'bmp280', 'mpu6050', 'gy511', 'gpsm6n',
                'sikap', 'sikap_gps', or 'all'
            verbose: Enable verbose LoRa output
            read_gps_hardware: If False, skip GPSM6N hardware init/read even when
                sensor mode is gpsm6n/sikap_gps/all (useful when GPS is unplugged)
            
        Raises:
            ValueError: If invalid sensor type is specified
            ImportError: If required sensor libraries are not installed
        """
        if sensors not in self.VALID_SENSORS:
            raise ValueError(
                f"Invalid sensor type: '{sensors}'. "
                f"Must be one of: {self.VALID_SENSORS}"
            )
        
        self.sensors = sensors
        self.verbose = verbose
        self.bmp = None
        self.mpu = None
        self.gy511 = None
        self.gps = None
        self.read_gps_hardware = bool(read_gps_hardware)

        # Setup GPIO (encapsulated here so caller doesn't need to manage it)
        setup_gpio()

        # Initialize requested sensors
        if sensors in ('bmp280', 'sikap', 'sikap_gps', 'all'):
            BMP280Class = _import_bmp280()
            self.bmp = BMP280Class()
            print("[INFO] BMP280 sensor initialized.")
        
        if sensors in ('mpu6050', 'sikap', 'sikap_gps', 'all'):
            MPU6050Class = _import_mpu6050()
            self.mpu = MPU6050Class()
            print("[INFO] MPU6050 sensor initialized.")
        
        if sensors in ('gy511', 'sikap', 'sikap_gps', 'all'):
            GY511Class = _import_gy511()
            self.gy511 = GY511Class()
            print("[INFO] GY-511 sensor initialized.")

        if sensors in ('gpsm6n', 'sikap_gps', 'all'):
            if self.read_gps_hardware:
                GPSM6NClass = _import_gpsm6n()
                self.gps = GPSM6NClass()
                print("[INFO] GPSM6N sensor initialized.")
            else:
                print("[INFO] GPSM6N hardware read disabled.")
        
        # Initialize LoRa sender
        self.lora = LoRaSender(verbose=verbose)
        self.lora.configure()
        print("[INFO] LoRa sender initialized.")
    
    def baca_data(self):
        """
        Read data from all configured sensors.
        
        Returns:
            dict: Dictionary containing sensor data with keys:
                - 'bmp280': dict with 'suhu', 'tekanan', 'ketinggian' (if BMP280 enabled)
                - 'mpu6050': dict with 'akselerasi', 'gyroscope', 'suhu' (if MPU6050 enabled)
                - 'gy511': dict with 'orientasi' (pitch, roll, heading in degrees) (if GY511 enabled)
                - 'gpsm6n': dict with 'latitude', 'longitude', 'status' (if GPSM6N enabled)
        """
        data = {}
        
        if self.bmp is not None:
            data['bmp280'] = self.bmp.baca_semua()
        
        if self.mpu is not None:
            data['mpu6050'] = self.mpu.baca_semua()
        
        if self.gy511 is not None:
            data['gy511'] = self.gy511.baca_semua()

        if self.gps is not None:
            data['gpsm6n'] = self.gps.baca_semua()
        
        return data
    
    def format_pesan(self, data, counter, gps_override=None):
        """
        Format sensor data into a compact LoRa message string.
        
        Message format depends on which sensors are enabled:
        - BMP280: "S:25.5C T:1010.5hPa K:50.2m"
        - MPU6050: "P:10.5 R:-5.2 GX:1.0/s GY:0.5/s GZ:0.0/s" (Pitch, Roll, Gyro in degrees)
        - GY511: "P:10.5 R:-5.2 H:90.0" (Pitch, Roll, Heading in degrees)
        - All: "#{counter} | S:25.5C T:1010.5 K:50.2 | P:10.5 R:-5.2 H:90.0"
        
        Args:
            data: Dictionary from baca_data()
            counter: Message sequence counter
            
        Returns:
            str: Formatted message string for LoRa transmission
        """
        if self.sensors == 'sikap':
            mpu_orientasi = data['mpu6050']['orientasi']
            gy_orientasi = data['gy511']['orientasi']
            bmp_data = data['bmp280']

            timestamp = int(time.time())
            return (
                f"waktu_kirim:{timestamp} "
                f"pitch:{mpu_orientasi['pitch']} roll:{mpu_orientasi['roll']} "
                f"yaw:{gy_orientasi['heading']} "
                f"tekanan:{bmp_data['tekanan']}hPa ketinggian:{bmp_data['ketinggian']}m"
            )

        if self.sensors == 'sikap_gps':
            mpu_orientasi = data['mpu6050']['orientasi']
            gy_orientasi = data['gy511']['orientasi']
            bmp_data = data['bmp280']

            gps_data = data.get('gpsm6n', {})
            if isinstance(gps_override, dict):
                gps_data = {
                    "lintang": gps_override.get('latitude'),
                    "bujur": gps_override.get('longitude'),
                    "iterasi": gps_override.get('iterasi'),
                    "selesai": gps_override.get('finish'),
                    "misi_status": gps_override.get('mission_status', 'Meluncur'),
                    "ditemukan": gps_override.get('found', False),
                    "id_misi": gps_override.get('id_misi', ''),
                }
            else:
                # Normalisasi field dari hardware GPS ke format misi baru
                gps_data = {
                    "lintang": gps_data.get('latitude'),
                    "bujur": gps_data.get('longitude'),
                    "iterasi": gps_data.get('iterasi'),
                    "selesai": gps_data.get('finish'),
                    "misi_status": gps_data.get('mission_status', 'Launch'),
                    "ditemukan": gps_data.get('found', False),
                    "id_misi": gps_data.get('id_misi', ''),
                }

            timestamp = int(time.time())
            iterasi = gps_data.get('iterasi')
            selesai = gps_data.get('selesai')
            misi_status = gps_data.get('misi_status', 'Launch')
            ditemukan = bool(gps_data.get('ditemukan', False))

            prefix = ""
            if iterasi is not None and selesai is not None:
                prefix = f"iterasi:{iterasi} selesai:{selesai} "

            return (
                f"{prefix}waktu_kirim:{timestamp} "
                f"pitch:{mpu_orientasi['pitch']} roll:{mpu_orientasi['roll']} "
                f"yaw:{gy_orientasi['heading']} "
                f"tekanan:{bmp_data['tekanan']}hPa ketinggian:{bmp_data['ketinggian']}m "
                f"lintang:{gps_data.get('lintang')} bujur:{gps_data.get('bujur')} "
                f"misi_status:{misi_status} ditemukan:{ditemukan} "
                f"id_misi:{gps_data.get('id_misi', '')}"
            )

        parts = [f"#{counter}"]
        
        if 'bmp280' in data:
            bmp = data['bmp280']
            parts.append(f"S:{bmp['suhu']}C T:{bmp['tekanan']}hPa K:{bmp['ketinggian']}m")
        
        if 'mpu6050' in data:
            mpu = data['mpu6050']
            orientasi = mpu['orientasi']
            parts.append(
                f"P:{orientasi['pitch']} R:{orientasi['roll']} "
                f"GX:{orientasi['gx_dps']}/s GY:{orientasi['gy_dps']}/s GZ:{orientasi['gz_dps']}/s"
            )
        
        if 'gy511' in data:
            gy511 = data['gy511']
            orientasi = gy511['orientasi']
            parts.append(
                f"P:{orientasi['pitch']} R:{orientasi['roll']} H:{orientasi['heading']}"
            )

        if 'gpsm6n' in data:
            gps = data['gpsm6n']
            parts.append(
                f"LAT:{gps.get('latitude')} LON:{gps.get('longitude')} "
                f"SAT:{gps.get('satellites', 0)} FIX:{gps.get('status')}"
            )
        
        return " | ".join(parts)
    
    def kirim_data(self, counter, gps_override=None, timeout=None):
        """
        Read sensors and send data via LoRa.
        
        Args:
            counter: Message sequence counter
            gps_override: Optional GPS override for mission route
            timeout: Optional TX timeout in seconds
            
        Returns:
            tuple: (success: bool, message: str)
                - success: True if message was sent successfully
                - message: The formatted message that was sent
        """
        data = self.baca_data()
        pesan = self.format_pesan(data, counter, gps_override=gps_override)
        sukses = self.lora.kirim(pesan, timeout=timeout)
        return sukses, pesan
    
    def run(self, interval=1):
        """
        Main loop: continuously read sensors and send data via LoRa.
        
        Args:
            interval: Seconds between transmissions (default: 2)
        """
        counter = 1
        sensor_info = self.sensors.upper()
        print(f"\n[INFO] LoRa Sensor Sender Ready! (Sensors: {sensor_info})\n")
        
        try:
            while True:
                sukses, pesan = self.kirim_data(counter)
                
                print(f"Mengirim : {pesan}")
                if sukses:
                    print("Status   : Terkirim!")
                else:
                    print("Status   : Gagal terkirim (Timeout)")
                print("-" * 60)
                
                counter += 1
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n[INFO] Program dihentikan oleh pengguna.")
    
    def cleanup(self):
        """Cleanup LoRa resources."""
        if self.gps is not None:
            try:
                self.gps.close()
            except Exception:
                pass
        teardown_gpio(self.lora)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="LoRa Sensor Data Sender - Transmit sensor data via LoRa radio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m finalCode.lora.sender_sensor --sensor bmp280
    python -m finalCode.lora.sender_sensor --sensor mpu6050
    python -m finalCode.lora.sender_sensor --sensor gy511
    python -m finalCode.lora.sender_sensor --sensor gpsm6n
    python -m finalCode.lora.sender_sensor --sensor sikap
    python -m finalCode.lora.sender_sensor --sensor sikap_gps
    python -m finalCode.lora.sender_sensor --sensor all --interval 5
        """
    )
    
    parser.add_argument(
        '--sensor',
        choices=['bmp280', 'mpu6050', 'gy511', 'gpsm6n', 'sikap', 'sikap_gps', 'all'],
        default='all',
        help="Which sensor(s) to use (default: all)"
    )
    
    parser.add_argument(
        '--interval',
        type=float,
        default=2.0,
        help="Seconds between transmissions (default: 2)"
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help="Enable verbose LoRa output"
    )
    
    args = parser.parse_args()

    sender = None
    try:
        # Initialize sender — GPIO setup is encapsulated inside LoRaSensorSender.__init__
        print(f"[INFO] Initializing sensors: {args.sensor}")
        sender = LoRaSensorSender(sensors=args.sensor, verbose=args.verbose)
        
        # Run main loop
        sender.run(interval=args.interval)
    
    except ImportError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)
    
    finally:
        if sender is not None:
            sender.cleanup()


if __name__ == "__main__":
    main()
