"""
BMP280 Sensor Module

Provides the SensorBMP280 class for interfacing with the BMP280
temperature, pressure, and altitude sensor via I2C.

Requirements:
    - adafruit-circuitpython-bmp280
    - board
    - busio

Usage:
    from sensor.bmp280 import SensorBMP280
    
    sensor = SensorBMP280()
    data = sensor.baca_semua()
    sensor.tampilkan()
"""

import time
import board
import busio
import adafruit_bmp280


class SensorBMP280:
    """
    Interface for BMP280 temperature, pressure, and altitude sensor.
    
    Attributes:
        i2c: I2C bus interface
        sensor: BMP280 sensor instance
        
    Args:
        scl: SCL pin (default: board.SCL)
        sda: SDA pin (default: board.SDA)
        address: I2C address (default: 0x76)
        sea_level_pressure: Sea level pressure in hPa for altitude calculation (default: 1013.25)
    """
    
    def __init__(self, scl=board.SCL, sda=board.SDA, address=0x76, sea_level_pressure=1013.25):
        """Initialize BMP280 sensor on I2C bus."""
        self.i2c = busio.I2C(scl, sda)
        self.sensor = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c, address=address)
        self.sensor.sea_level_pressure = sea_level_pressure

    def baca_suhu(self):
        """
        Read temperature from sensor.
        
        Returns:
            float: Temperature in Celsius, rounded to 2 decimal places
        """
        return round(self.sensor.temperature, 2)

    def baca_tekanan(self):
        """
        Read pressure from sensor.
        
        Returns:
            float: Pressure in hPa, rounded to 2 decimal places
        """
        return round(self.sensor.pressure, 2)

    def baca_ketinggian(self):
        """
        Read altitude from sensor (calculated from pressure).
        
        Returns:
            float: Altitude in meters, rounded to 2 decimal places
        """
        return round(self.sensor.altitude, 2)

    def baca_semua(self):
        """
        Read all sensor data.
        
        Returns:
            dict: Dictionary containing 'suhu', 'tekanan', and 'ketinggian'
        """
        return {
            "suhu": self.baca_suhu(),
            "tekanan": self.baca_tekanan(),
            "ketinggian": self.baca_ketinggian()
        }

    def tampilkan(self):
        """Display all sensor readings to console."""
        data = self.baca_semua()
        print(f"Suhu       : {data['suhu']} C")
        print(f"Tekanan    : {data['tekanan']} hPa")
        print(f"Ketinggian : {data['ketinggian']} m")
        print("-" * 30)


if __name__ == "__main__":
    bmp = SensorBMP280()
    print("BMP280 siap dibaca\n")

    try:
        while True:
            bmp.tampilkan()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
