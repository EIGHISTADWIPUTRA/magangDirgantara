import sys
import RPi.GPIO as GPIO
from SX127x.LoRa import *
from SX127x.board_config import BOARD

GPIO.setwarnings(False)
GPIO.cleanup()
BOARD.setup()

class LoRaCheck(LoRa):
    def __init__(self, verbose=False):
        super(LoRaCheck, self).__init__(verbose)

try:
    lora = LoRaCheck(verbose=False)
    
    version = lora.get_version()
    
    if version == 18:  # 0x12 = 18, versi valid SX127x
        print(f"LoRa SEHAT - Terdeteksi (Version register: 0x{version:02X})")
    else:
        print(f"LoRa terbaca tapi version tidak dikenal (0x{version:02X})")

except Exception as e:
    print(f"LoRa TIDAK TERBACA - Error: {e}")

finally:
    try:
        lora.set_mode(MODE.SLEEP)
    except:
        pass
    BOARD.teardown()

