import time
import board
import busio
import adafruit_bmp280

class SensorBMP280:
    def __init__(self, scl=board.SCL, sda=board.SDA):
        self.i2c = busio.I2C(scl, sda)
        self.sensor = adafruit_bmp280.Adafruit_BMP280_I2C(self.i2c, address=0x76)
        self.sensor.sea_level_pressure = 1013.25

    def baca_suhu(self):
        return round(self.sensor.temperature, 2)

    def baca_tekanan(self):
        return round(self.sensor.pressure, 2)

    def baca_ketinggian(self):
        return round(self.sensor.altitude, 2)

    def baca_semua(self):
        return {
            "suhu"      : self.baca_suhu(),
            "tekanan"   : self.baca_tekanan(),
            "ketinggian": self.baca_ketinggian()
        }

    def tampilkan(self):
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
