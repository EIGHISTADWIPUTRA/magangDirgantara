"""
LoRa Sender Module.

This module provides a basic LoRa message sender using the SX127x chipset.
Extends the base LoRa class to enable simple message transmission.

Configuration:
    - Frequency: 433.0 MHz
    - Sync Word: 0x12
    - Spreading Factor: 7
    - Bandwidth: 250 kHz
    - Coding Rate: CR4_5

Example:
    >>> lora = LoRaSender(verbose=False)
    >>> lora.configure()
    >>> lora.kirim("Hello World")
    True
"""

import sys
import time
import RPi.GPIO as GPIO
from SX127x.LoRa import *
from SX127x.board_config import BOARD


class LoRaSender(LoRa):
    """
    LoRa message sender class.
    
    Extends the base LoRa class to provide simple message transmission
    capabilities with TX_DONE confirmation.
    
    Attributes:
        verbose (bool): Enable verbose output for debugging.
    """
    
    # Default LoRa configuration
    DEFAULT_FREQ = 433.0
    DEFAULT_SYNC_WORD = 0x12
    DEFAULT_SF = 7
    DEFAULT_BW = BW.BW250
    DEFAULT_CR = CODING_RATE.CR4_5
    DEFAULT_TX_TIMEOUT = 5
    
    def __init__(self, verbose=False):
        """
        Initialize the LoRa sender.
        
        Args:
            verbose (bool): Enable verbose output. Default is False.
        """
        super(LoRaSender, self).__init__(verbose)
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([1, 0, 0, 0, 0, 0])
    
    def configure(self, freq=None, sync_word=None, sf=None, bw=None, cr=None):
        """
        Configure LoRa parameters.
        
        Args:
            freq (float): Frequency in MHz. Default is 433.0.
            sync_word (int): Sync word for communication. Default is 0xF3.
            sf (int): Spreading factor (6-12). Default is 7.
            bw: Bandwidth constant. Default is BW.BW125.
            cr: Coding rate constant. Default is CODING_RATE.CR4_5.
        """
        self.set_pa_config(pa_select=1)
        self.set_freq(freq if freq is not None else self.DEFAULT_FREQ)
        self.set_sync_word(sync_word if sync_word is not None else self.DEFAULT_SYNC_WORD)
        self.set_spreading_factor(sf if sf is not None else self.DEFAULT_SF)
        self.set_bw(bw if bw is not None else self.DEFAULT_BW)
        self.set_coding_rate(cr if cr is not None else self.DEFAULT_CR)
    
    def kirim(self, pesan, timeout=None):
        """
        Send a message via LoRa.
        
        Transmits the message and waits for TX_DONE confirmation.
        
        Args:
            pesan (str): The message to send.
            timeout (int): Timeout in seconds. Default is 5.
            
        Returns:
            bool: True if message was sent successfully, False on timeout.
        """
        if timeout is None:
            timeout = self.DEFAULT_TX_TIMEOUT
            
        self.write_payload(list(pesan.encode('utf-8')))
        self.set_mode(MODE.TX)
        
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


def setup_gpio():
    """Setup GPIO, BOARD, and SPI for LoRa communication."""
    from SX127x.LoRa import LoRa as LoRaBase
    
    GPIO.setwarnings(False)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    BOARD.setup()
    
    # Reinitialize SPI (LoRa.spi is class-level, only set once at import)
    # We need to explicitly recreate SPI after GPIO cleanup
    BOARD.SpiDev()
    LoRaBase.spi = BOARD.spi


def teardown_gpio(lora):
    """Cleanup GPIO and put LoRa to sleep."""
    lora.set_mode(MODE.SLEEP)
    BOARD.teardown()
    try:
        BOARD.spi = None
    except:
        pass


def check_health():
    """
    Check LoRa module health.
    
    Handles the FULL SPI lifecycle: setup GPIO, reinitialize SPI,
    create LoRa instance, read version, cleanup.
    
    Returns:
        dict: Status info with keys:
            - 'status': 'SEHAT', 'WARNING', or 'TIDAK TERBACA'
            - 'version': Version hex string (if readable)
            - 'chip': Chip name (if healthy)
            - 'message': Error message (if not healthy)
    """
    gpio_initialized = False
    try:
        # Full fresh setup - clean any previous state first
        GPIO.setwarnings(False)
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        BOARD.setup()
        gpio_initialized = True
        
        # Reinitialize SPI (LoRa.spi is a class-level var, only set once at import)
        # We need to explicitly recreate SPI after GPIO cleanup
        BOARD.SpiDev()
        
        # Import the base LoRa class and update its SPI reference
        from SX127x.LoRa import LoRa as LoRaBase
        LoRaBase.spi = BOARD.spi
        
        class _LoRaCheck(LoRaBase):
            def __init__(self):
                super().__init__(verbose=False)
        
        lora = _LoRaCheck()
        version = lora.get_version()
        lora.set_mode(MODE.SLEEP)
        
        # Version 0x12 (18) is valid SX127x version
        if version == 18:
            return {'status': 'SEHAT', 'version': f'0x{version:02X}', 'chip': 'SX127x'}
        else:
            return {'status': 'WARNING', 'version': f'0x{version:02X}', 'message': 'Version tidak dikenal'}
    except Exception as e:
        return {'status': 'TIDAK TERBACA', 'message': str(e)}
    finally:
        if gpio_initialized:
            try:
                BOARD.teardown()
            except:
                pass
            try:
                BOARD.spi = None
            except:
                pass
            try:
                GPIO.cleanup()
            except:
                pass


if __name__ == "__main__":
    # Setup GPIO and BOARD
    setup_gpio()
    
    # Initialize LoRa sender
    lora = LoRaSender(verbose=False)
    lora.configure()
    
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
        teardown_gpio(lora)
