"""
LoRa Ping-Pong Communication Module.

This module provides bidirectional LoRa communication with ping-pong
functionality. Sends PING messages and waits for PONG responses,
measuring RSSI and SNR for link quality assessment.

Configuration:
    - Frequency: 433.0 MHz
    - Sync Word: 0xF3
    - Spreading Factor: 7
    - Bandwidth: 125 kHz
    - Coding Rate: CR4_5

Example:
    >>> lora = LoRaPingPong(verbose=False)
    >>> lora.configure()
    >>> lora.start()  # Starts the ping-pong loop
"""

import sys
import time
import RPi.GPIO as GPIO
from SX127x.LoRa import *
from SX127x.board_config import BOARD


class LoRaPingPong(LoRa):
    """
    LoRa ping-pong communication class.
    
    Extends the base LoRa class to provide bidirectional communication
    with PING/PONG message exchange and signal quality measurement.
    
    Attributes:
        verbose (bool): Enable verbose output for debugging.
        counter (int): Message counter for tracking exchanges.
    """
    
    # Default LoRa configuration
    DEFAULT_FREQ = 433.0
    DEFAULT_SYNC_WORD = 0xF3
    DEFAULT_SF = 7
    DEFAULT_BW = BW.BW125
    DEFAULT_CR = CODING_RATE.CR4_5
    DEFAULT_TX_TIMEOUT = 5
    DEFAULT_RX_TIMEOUT = 10
    
    def __init__(self, verbose=False):
        """
        Initialize the LoRa ping-pong transceiver.
        
        Args:
            verbose (bool): Enable verbose output. Default is False.
        """
        super(LoRaPingPong, self).__init__(verbose)
        self.counter = 0
        self.set_mode(MODE.SLEEP)
        self.set_dio_mapping([0] * 6)
    
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
            
        self.set_mode(MODE.STDBY)
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
    
    def tunggu_terima(self, timeout=None):
        """
        Wait to receive a message via LoRa.
        
        Listens for incoming messages and returns the message with
        signal quality metrics (RSSI and SNR).
        
        Args:
            timeout (int): Timeout in seconds. Default is 10.
            
        Returns:
            tuple: (message, rssi, snr) if received, (None, None, None) on timeout.
                - message (str): Received message string.
                - rssi (int): Received Signal Strength Indicator in dBm.
                - snr (float): Signal-to-Noise Ratio in dB.
        """
        if timeout is None:
            timeout = self.DEFAULT_RX_TIMEOUT
            
        self.reset_ptr_rx()
        self.set_mode(MODE.RXCONT)
        
        start = time.time()
        while True:
            irq_flags = self.get_irq_flags()
            if irq_flags.get('rx_done', False):
                self.clear_irq_flags(RxDone=1)
                payload = self.read_payload(nocheck=True)
                pesan = bytes(payload).decode('utf-8', 'ignore')
                rssi = self.get_rssi_value()
                snr = self.get_pkt_snr_value()
                self.set_mode(MODE.STDBY)
                return pesan, rssi, snr
            if time.time() - start > timeout:
                self.set_mode(MODE.STDBY)
                return None, None, None
            time.sleep(0.01)
    
    def start(self):
        """
        Start the ping-pong communication loop.
        
        Continuously sends PING messages and waits for PONG responses,
        displaying signal quality metrics for each exchange.
        """
        print("Raspberry Pi siap, mulai kirim PING ke Arduino...\n")
        
        while True:
            self.counter += 1
            
            # Send PING to Arduino
            print(f"[{self.counter}] Kirim : PING")
            sukses = self.kirim("PING")
            
            if not sukses:
                print("Gagal kirim, coba lagi...")
                time.sleep(2)
                continue
            
            # Wait for response from Arduino
            print(f"[{self.counter}] Menunggu balasan...")
            pesan_balas, rssi, snr = self.tunggu_terima()
            
            if pesan_balas:
                print(f"[{self.counter}] Terima : {pesan_balas}")
                print(f"[{self.counter}] RSSI   : {rssi} dBm | SNR: {snr} dB")
            else:
                print(f"[{self.counter}] Timeout, tidak ada balasan dari Arduino")
            
            print("-" * 40)
            time.sleep(2)


def setup_gpio():
    """Setup GPIO and BOARD for LoRa communication."""
    GPIO.setwarnings(False)
    GPIO.cleanup()
    BOARD.setup()


def teardown_gpio(lora):
    """Cleanup GPIO and put LoRa to sleep."""
    lora.set_mode(MODE.SLEEP)
    BOARD.teardown()


if __name__ == "__main__":
    # Setup GPIO and BOARD
    setup_gpio()
    
    # Initialize LoRa ping-pong
    lora = LoRaPingPong(verbose=False)
    lora.configure()
    
    try:
        lora.start()
    
    except KeyboardInterrupt:
        print("\nProgram dihentikan.")
    
    finally:
        teardown_gpio(lora)
