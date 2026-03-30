import sys
import time
import RPi.GPIO as GPIO
from SX127x.LoRa import *
from SX127x.board_config import BOARD

GPIO.setwarnings(False)
GPIO.cleanup()          # cleanup dulu
GPIO.setmode(GPIO.BCM)  # baru setmode
BOARD.setup()

class LoRaSender(LoRa):
    def __init__(self, verbose=False):
        super(LoRaSender, self).__init__(verbose)
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([1, 0, 0, 0, 0, 0])

    def kirim(self, pesan):
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


lora = LoRaSender(verbose=False)
lora.set_pa_config(pa_select=1)
lora.set_freq(433.0)
lora.set_sync_word(0xF3)
lora.set_spreading_factor(7)
lora.set_bw(BW.BW125)
lora.set_coding_rate(CODING_RATE.CR4_5)

counter = 1
print("Raspberry Pi Sender siap!\n")

try:
    while True:
        pesan = f"counter:{counter} | {time.strftime('%H:%M:%S')}"
        print(f"Mengirim : {pesan}")
        sukses = lora.kirim(pesan)
        if sukses:
            print("Terkirim!")
        else:
            print("Gagal terkirim")
        print("-" * 40)
        counter += 1
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nProgram dihentikan.")

finally:
    lora.set_mode(MODE.SLEEP)
    BOARD.teardown()
