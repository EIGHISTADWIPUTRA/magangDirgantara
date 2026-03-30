import sys
import time
import RPi.GPIO as GPIO
from SX127x.LoRa import *
from SX127x.board_config import BOARD

GPIO.setwarnings(False)
GPIO.cleanup()
BOARD.setup()

class LoRaPingPong(LoRa):
    def __init__(self, verbose=False):
        super(LoRaPingPong, self).__init__(verbose)
        self.counter = 0
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0] * 6)

    def kirim(self, pesan):
        self.set_mode(MODE.STDBY)
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

    def tunggu_terima(self, timeout=10):
        self.reset_ptr_rx()
        self.set_mode(MODE.RXCONT)

        start = time.time()
        while True:
            irq_flags = self.get_irq_flags()
            if irq_flags.get('rx_done', False):
                self.clear_irq_flags(RxDone=1)
                payload = self.read_payload(nocheck=True)
                pesan = bytes(payload).decode('utf-8', 'ignore')
                rssi  = self.get_rssi_value()
                snr   = self.get_pkt_snr_value()
                self.set_mode(MODE.STDBY)
                return pesan, rssi, snr
            if time.time() - start > timeout:
                self.set_mode(MODE.STDBY)
                return None, None, None
            time.sleep(0.01)

    def start(self):
        print("Raspberry Pi siap, mulai kirim PING ke Arduino...\n")
        while True:
            self.counter += 1

            # Kirim PING ke Arduino
            print(f"[{self.counter}] Kirim : PING")
            sukses = self.kirim("PING")
            if not sukses:
                print("Gagal kirim, coba lagi...")
                time.sleep(2)
                continue

            # Tunggu balasan dari Arduino
            print(f"[{self.counter}] Menunggu balasan...")
            pesan_balas, rssi, snr = self.tunggu_terima(timeout=10)

            if pesan_balas:
                print(f"[{self.counter}] Terima : {pesan_balas}")
                print(f"[{self.counter}] RSSI   : {rssi} dBm | SNR: {snr} dB")
            else:
                print(f"[{self.counter}] Timeout, tidak ada balasan dari Arduino")

            print("-" * 40)
            time.sleep(2)


lora = LoRaPingPong(verbose=False)
lora.set_pa_config(pa_select=1)
lora.set_freq(433.0)          # sama dengan Arduino: 433E6
lora.set_sync_word(0xF3)      # sama dengan Arduino: setSyncWord(0xF3)
lora.set_spreading_factor(7)
lora.set_bw(BW.BW125)
lora.set_coding_rate(CODING_RATE.CR4_5)

try:
    lora.start()
except KeyboardInterrupt:
    print("\nProgram dihentikan.")
finally:
    lora.set_mode(MODE.SLEEP)
    BOARD.teardown()
