"""
GPS M6N Sensor Module

Provides the SensorGPSM6N class for reading NMEA data from a u-blox GPS M6N
module over serial connection.

Requirements:
    - pyserial

Usage:
    from sensor.gpsm6n import SensorGPSM6N

    gps = SensorGPSM6N()
    data = gps.baca_semua()
    gps.tampilkan()
"""

import time


class SensorGPSM6N:
    """
    Interface for GPS M6N module using NMEA sentences.

    Args:
        port: Serial device path (default: /dev/ttyAMA0)
        baudrate: Serial baudrate (default: 9600)
        timeout: Serial timeout in seconds (default: 1.0)
        max_reads: Maximum serial reads per query (default: 40)
    """

    def __init__(self, port='/dev/serial0', baudrate=9600, timeout=1.0, max_reads=40):
        try:
            import serial
        except ImportError as e:
            raise ImportError(
                "Failed to import serial module. Install required package: pyserial. "
                f"Error: {e}"
            )

        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        self.port = port
        self.baudrate = baudrate
        self.max_reads = max_reads

    @staticmethod
    def _ddmm_to_decimal(raw_value, direction):
        """Convert NMEA ddmm.mmmm format to decimal degrees."""
        if not raw_value:
            return None

        value = float(raw_value)
        degrees = int(value / 100)
        minutes = value - (degrees * 100)
        decimal = degrees + (minutes / 60.0)

        if direction in ('S', 'W'):
            decimal *= -1

        return round(decimal, 6)

    def _parse_gga(self, fields):
        """Parse GPGGA/GNGGA sentence fields."""
        if len(fields) < 15:
            return {}

        lat = self._ddmm_to_decimal(fields[2], fields[3]) if fields[2] else None
        lon = self._ddmm_to_decimal(fields[4], fields[5]) if fields[4] else None

        fix_quality = int(fields[6]) if fields[6].isdigit() else 0
        satellites = int(fields[7]) if fields[7].isdigit() else 0
        hdop = float(fields[8]) if fields[8] else None
        altitude = float(fields[9]) if fields[9] else None

        return {
            'latitude': lat,
            'longitude': lon,
            'fix_quality': fix_quality,
            'satellites': satellites,
            'hdop': hdop,
            'altitude': round(altitude, 2) if altitude is not None else None,
            'has_fix': fix_quality > 0,
            'utc_time': fields[1] if fields[1] else None,
        }

    def _parse_rmc(self, fields):
        """Parse GPRMC/GNRMC sentence fields."""
        if len(fields) < 12:
            return {}

        status = fields[2]
        lat = self._ddmm_to_decimal(fields[3], fields[4]) if fields[3] else None
        lon = self._ddmm_to_decimal(fields[5], fields[6]) if fields[5] else None

        speed_knots = float(fields[7]) if fields[7] else 0.0
        course = float(fields[8]) if fields[8] else None

        return {
            'latitude': lat,
            'longitude': lon,
            'speed_knots': round(speed_knots, 2),
            'speed_kmh': round(speed_knots * 1.852, 2),
            'course': round(course, 2) if course is not None else None,
            'status': status,
            'has_fix': status == 'A',
            'utc_time': fields[1] if fields[1] else None,
            'utc_date': fields[9] if fields[9] else None,
        }

    def _read_sentence(self):
        """Read one NMEA sentence from serial port."""
        raw = self._serial.readline()
        if not raw:
            return ''
        return raw.decode('ascii', errors='ignore').strip()

    def baca_semua(self):
        """
        Read latest GPS data from available NMEA sentences.

        Returns:
            dict: GPS information with fix status and position data
        """
        latest = {
            'status': 'NO_FIX',
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'satellites': 0,
            'speed_kmh': 0.0,
            'course': None,
            'hdop': None,
            'source': None,
            'port': self.port,
            'baudrate': self.baudrate,
        }

        # Collect a few NMEA sentences and keep the latest valid fields.
        for _ in range(self.max_reads):
            sentence = self._read_sentence()
            if not sentence.startswith('$'):
                continue

            fields = sentence.split(',')
            sentence_type = fields[0]

            if sentence_type in ('$GPGGA', '$GNGGA'):
                parsed = self._parse_gga(fields)
                if not parsed:
                    continue
                latest.update({
                    'latitude': parsed.get('latitude', latest['latitude']),
                    'longitude': parsed.get('longitude', latest['longitude']),
                    'altitude': parsed.get('altitude', latest['altitude']),
                    'satellites': parsed.get('satellites', latest['satellites']),
                    'hdop': parsed.get('hdop', latest['hdop']),
                    'utc_time': parsed.get('utc_time', latest.get('utc_time')),
                    'source': 'GGA',
                })
                if parsed.get('has_fix'):
                    latest['status'] = 'FIX'

            elif sentence_type in ('$GPRMC', '$GNRMC'):
                parsed = self._parse_rmc(fields)
                if not parsed:
                    continue
                latest.update({
                    'latitude': parsed.get('latitude', latest['latitude']),
                    'longitude': parsed.get('longitude', latest['longitude']),
                    'speed_kmh': parsed.get('speed_kmh', latest['speed_kmh']),
                    'course': parsed.get('course', latest['course']),
                    'utc_time': parsed.get('utc_time', latest.get('utc_time')),
                    'utc_date': parsed.get('utc_date', latest.get('utc_date')),
                    'source': 'RMC',
                })
                if parsed.get('has_fix'):
                    latest['status'] = 'FIX'

            if latest['status'] == 'FIX' and latest['latitude'] is not None and latest['longitude'] is not None:
                break

        return latest

    def tampilkan(self):
        """Display GPS readings to console."""
        data = self.baca_semua()
        print("=== Data GPS M6N ===")
        print(f"Status     : {data['status']}")
        print(f"Latitude   : {data['latitude']}")
        print(f"Longitude  : {data['longitude']}")
        print(f"Altitude   : {data['altitude']} m")
        print(f"Satellites : {data['satellites']}")
        print(f"Speed      : {data['speed_kmh']} km/h")
        print(f"Course     : {data['course']}")
        print(f"Source     : {data['source']}")
        print("-" * 30)

    def close(self):
        """Close serial connection."""
        if self._serial is not None and self._serial.is_open:
            self._serial.close()


if __name__ == "__main__":
    gps = SensorGPSM6N()
    print("GPS M6N siap dibaca\n")

    try:
        while True:
            gps.tampilkan()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
    finally:
        gps.close()
