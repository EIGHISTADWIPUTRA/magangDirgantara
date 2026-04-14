import time
import board
import busio
import adafruit_mpu6050

class SensorMPU6050:
    def __init__(self, scl=board.SCL, sda=board.SDA, address=0x68):
        self.i2c = busio.I2C(scl, sda)
        self.sensor = adafruit_mpu6050.MPU6050(self.i2c, address=address)
        
    def baca_akselerasi(self):
        """Membaca data akselerometer (m/s^2)"""
        ax, ay, az = self.sensor.acceleration
        return {
            "ax": round(ax, 2),
            "ay": round(ay, 2),
            "az": round(az, 2)
        }
    
    def baca_gyroscope(self):
        """Membaca data gyroscope (rad/s)"""
        gx, gy, gz = self.sensor.gyro
        return {
            "gx": round(gx, 2),
            "gy": round(gy, 2),
            "gz": round(gz, 2)
        }
    
    def baca_suhu(self):
        """Membaca suhu internal sensor (Celsius)"""
        return round(self.sensor.temperature, 2)
    
    def baca_semua(self):
        """Membaca semua data sensor"""
        accel = self.baca_akselerasi()
        gyro = self.baca_gyroscope()
        return {
            "akselerasi": accel,
            "gyroscope": gyro,
            "suhu": self.baca_suhu()
        }
    
    def tampilkan(self):
        """Menampilkan semua data sensor ke konsol"""
        data = self.baca_semua()
        accel = data['akselerasi']
        gyro = data['gyroscope']
        
        print("=== Akselerometer (m/s²) ===")
        print(f"  X: {accel['ax']:>8.2f}")
        print(f"  Y: {accel['ay']:>8.2f}")
        print(f"  Z: {accel['az']:>8.2f}")
        
        print("=== Gyroscope (rad/s) ===")
        print(f"  X: {gyro['gx']:>8.2f}")
        print(f"  Y: {gyro['gy']:>8.2f}")
        print(f"  Z: {gyro['gz']:>8.2f}")
        
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
