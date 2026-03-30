import sys
import time
import board
import busio
import adafruit_bmp280
import RPi.GPIO as GPIO
from SX127x.LoRa import *
from SX127x.board_config import BOARD

# ==========================================
# SETUP GPIO & BOARD UNTUK LORA
# ==========================================
GPIO.setwarnings(False)
# Hapus GPIO.cleanup() di awal agar tidak error jika belum ada pin yang diset
GPIO.setmode(GPIO.BCM)  
BOARD.setup()

# ==========================================
# CLASS SENSOR BMP280
# ==========================================
class SensorBMP280:
    def __init__(self, scl=board.SCL, sda=board.SDA):
        self.i2c = busio.I2C(scl, sda)
        # Pastikan address sesuai (0x76 atau 0x77)
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

# ==========================================
# CLASS LORA SENDER
# ==========================================
class LoRaSender(LoRa):
    def __init__(self, verbose=False):
        super(LoRaSender, self).__init__(verbose)
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([1, 0, 0, 0, 0, 0])

    def kirim(self, pesan):
        # Mengubah string menjadi list of bytes
        self.write_payload(list(pesan.encode('utf-8')))
        self.set_mode(MODE.TX)

        timeout = 5
        start = time.time()
        while True:
            irq_flags = self.get_irq_flags()
            if irq_flags.get('tx_done', False):
                self.clear_irq_flags(TxDone=1)
                self.set_mode(MODE.STDBY)
                return True
            if time.time() - start > timeout:
                self.set_mode(MODE.STDBY)
                return False
            time.sleep(0.01)

# ==========================================
# PROGRAM UTAMA (MAIN)
# ==========================================
if __name__ == "__main__":
    # 1. Inisialisasi Sensor BMP280
    print("Inisialisasi Sensor BMP280...")
    bmp = SensorBMP280()
    
    # 2. Inisialisasi LoRa
    print("Inisialisasi Modul LoRa...")
    lora = LoRaSender(verbose=False)
    lora.set_pa_config(pa_select=1)
    lora.set_freq(433.0) # Pastikan frekuensi sesuai dengan receiver (misal 433 atau 915)
    lora.set_sync_word(0xF3)
    lora.set_spreading_factor(7)
    lora.set_bw(BW.BW125)
    lora.set_coding_rate(CODING_RATE.CR4_5)

    counter = 1
    print("\n[INFO] Sistem Sender LoRa + BMP280 Siap Berjalan!\n")

    try:
        while True:
            # Baca data dari sensor
            data = bmp.baca_semua()
            
            # Format pesan yang akan dikirim. 
            # Dibuat ringkas agar hemat payload LoRa.
            # Contoh hasil: "#1 | S: 25.5C, T: 1010.5hPa, K: 50.2m"
            pesan = f"#{counter} | S: {data['suhu']}C, T: {data['tekanan']}hPa, K: {data['ketinggian']}m"
            
            print(f"Mengirim : {pesan}")
            
            # Eksekusi pengiriman
            sukses = lora.kirim(pesan)
            
            if sukses:
                print("Status   : Terkirim!")
            else:
                print("Status   : Gagal terkirim (Timeout)")
            
            print("-" * 50)
            
            counter += 1
            # Jeda 2 detik antar pengiriman agar tidak membanjiri frekuensi
            time.sleep(2) 

    except KeyboardInterrupt:
        print("\n[INFO] Program dihentikan oleh pengguna.")

    finally:
        # Cleanup resource setelah selesai
        lora.set_mode(MODE.SLEEP)
        BOARD.teardown()
        GPIO.cleanup()
