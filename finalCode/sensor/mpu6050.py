"""
MPU6050 Sensor Module

Provides the SensorMPU6050 class for interfacing with the MPU-6050
accelerometer and gyroscope sensor via I2C.

Requirements:
    - adafruit-circuitpython-mpu6050
    - board
    - busio

Usage:
    from sensor.mpu6050 import SensorMPU6050
    
    sensor = SensorMPU6050()
    data = sensor.baca_semua()
    sensor.tampilkan()
"""

import time
import math
import board
import busio
import adafruit_mpu6050


class SensorMPU6050:
    """
    Interface for MPU-6050 accelerometer and gyroscope sensor.
    
    Attributes:
        i2c: I2C bus interface
        sensor: MPU6050 sensor instance
        
    Args:
        scl: SCL pin (default: board.SCL)
        sda: SDA pin (default: board.SDA)
        address: I2C address (default: 0x68)
    """
    
    def __init__(self, scl=board.SCL, sda=board.SDA, address=0x68):
        """Initialize MPU6050 sensor on I2C bus."""
        self.i2c = busio.I2C(scl, sda)
        self.sensor = adafruit_mpu6050.MPU6050(self.i2c, address=address)

    def baca_akselerasi(self):
        """
        Read accelerometer data from sensor.
        
        Returns:
            dict: Dictionary with 'ax', 'ay', 'az' values in m/s^2
        """
        ax, ay, az = self.sensor.acceleration
        return {
            "ax": round(ax, 2),
            "ay": round(ay, 2),
            "az": round(az, 2)
        }

    def baca_gyroscope(self):
        """
        Read gyroscope data from sensor.
        
        Returns:
            dict: Dictionary with 'gx', 'gy', 'gz' values in rad/s
        """
        gx, gy, gz = self.sensor.gyro
        return {
            "gx": round(gx, 2),
            "gy": round(gy, 2),
            "gz": round(gz, 2)
        }

    def baca_suhu(self):
        """
        Read internal temperature from sensor.
        
        Returns:
            float: Temperature in Celsius, rounded to 2 decimal places
        """
        return round(self.sensor.temperature, 2)

    def baca_orientasi(self):
        """
        Calculate orientation angles in degrees from accelerometer and gyroscope.
        
        - Pitch: Tilt forward/backward (-90° to +90°)
        - Roll: Tilt left/right (-180° to +180°)
        - Gyro X/Y/Z: Angular velocity in degrees/second
        
        Returns:
            dict: {'pitch': float, 'roll': float, 'gx_dps': float, 'gy_dps': float, 'gz_dps': float}
        """
        accel = self.baca_akselerasi()
        gyro = self.baca_gyroscope()
        
        ax, ay, az = accel['ax'], accel['ay'], accel['az']
        
        # Hitung Pitch dan Roll dari akselerometer
        pitch = math.atan2(-ax, math.sqrt(ay**2 + az**2)) * (180 / math.pi)
        roll  = math.atan2(ay, az) * (180 / math.pi)
        
        # Konversi gyroscope dari rad/s ke derajat/s
        gx_dps = round(gyro['gx'] * (180 / math.pi), 2)
        gy_dps = round(gyro['gy'] * (180 / math.pi), 2)
        gz_dps = round(gyro['gz'] * (180 / math.pi), 2)
        
        return {
            "pitch": round(pitch, 2),
            "roll": round(roll, 2),
            "gx_dps": gx_dps,
            "gy_dps": gy_dps,
            "gz_dps": gz_dps
        }

    def baca_semua(self):
        """
        Read all sensor data.
        
        Returns:
            dict: Dictionary containing 'akselerasi', 'gyroscope', 'orientasi', and 'suhu'
        """
        accel = self.baca_akselerasi()
        gyro = self.baca_gyroscope()
        return {
            "akselerasi": accel,
            "gyroscope": gyro,
            "orientasi": self.baca_orientasi(),
            "suhu": self.baca_suhu()
        }

    def tampilkan(self):
        """Display all sensor readings to console."""
        data = self.baca_semua()
        accel = data['akselerasi']
        gyro = data['gyroscope']
        orientasi = data['orientasi']
        
        print("=== Akselerometer (m/s²) ===")
        print(f"  X: {accel['ax']:>8.2f}")
        print(f"  Y: {accel['ay']:>8.2f}")
        print(f"  Z: {accel['az']:>8.2f}")
        
        print("=== Gyroscope (rad/s) ===")
        print(f"  X: {gyro['gx']:>8.2f}")
        print(f"  Y: {gyro['gy']:>8.2f}")
        print(f"  Z: {gyro['gz']:>8.2f}")
        
        print("=== Orientasi (Derajat) ===")
        print(f"  Pitch : {orientasi['pitch']:>7.2f}°")
        print(f"  Roll  : {orientasi['roll']:>7.2f}°")
        print(f"  Gyro X: {orientasi['gx_dps']:>7.2f} °/s")
        print(f"  Gyro Y: {orientasi['gy_dps']:>7.2f} °/s")
        print(f"  Gyro Z: {orientasi['gz_dps']:>7.2f} °/s")
        
        print(f"=== Suhu: {data['suhu']} °C ===")
        print("-" * 30)


if __name__ == "__main__":
    mpu = SensorMPU6050()
    print("MPU-6050 siap dibaca\n")

    try:
        while True:
            mpu.tampilkan()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
