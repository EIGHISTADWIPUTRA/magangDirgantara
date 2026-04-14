"""
Bluetooth Image Receiver untuk Raspberry Pi via Serial Port Profile (SPP)

Konfigurasi Raspberry Pi yang diperlukan sudah dilakukan:
1. Flag -C pada bluetoothd (compatibility mode)
2. sdptool add SP di dbus-org.bluez.service
3. rfcomm.service untuk menjalankan 'rfcomm watch hci0' saat booting
4. Koneksi Bluetooth otomatis dipetakan ke /dev/rfcomm0

Dependensi: pip install pyserial
"""

import os
import serial
import time
from datetime import datetime


class BluetoothImageReceiver:
    """
    Menerima gambar melalui Bluetooth SPP via /dev/rfcomm0.
    Koneksi Bluetooth ditangani oleh sistem (rfcomm.service).
    """
    
    def __init__(self, port='/dev/rfcomm0', baudrate=115200, save_folder='received_images'):
        self.port = port
        self.baudrate = baudrate
        self.save_folder = save_folder
        self.serial_conn = None
        
        # Buat folder penyimpanan jika belum ada
        if not os.path.exists(self.save_folder):
            os.makedirs(self.save_folder)
            print(f"[INFO] Folder '{self.save_folder}' dibuat")
    
    def wait_for_connection(self, timeout=None):
        """Menunggu koneksi Bluetooth tersedia di /dev/rfcomm0"""
        print(f"[INFO] Menunggu koneksi Bluetooth di {self.port}...")
        
        start_time = time.time()
        while True:
            if os.path.exists(self.port):
                try:
                    self.serial_conn = serial.Serial(
                        port=self.port,
                        baudrate=self.baudrate,
                        timeout=5
                    )
                    print(f"[INFO] Terhubung ke {self.port}")
                    return True
                except serial.SerialException as e:
                    print(f"[WARNING] Gagal membuka port: {e}")
                    time.sleep(1)
            else:
                if timeout and (time.time() - start_time) > timeout:
                    print("[ERROR] Timeout menunggu koneksi")
                    return False
                time.sleep(0.5)
    
    def receive_image(self):
        """
        Menerima gambar dari client Android.
        Protokol:
        1. Client mengirim header "IMG:" (4 bytes)
        2. Client mengirim ukuran file (8 bytes)
        3. Client mengirim ekstensi file (10 bytes)
        4. Client mengirim data gambar
        5. Server mengirim "OK" atau "FAIL"
        """
        try:
            # Tunggu header "IMG:"
            header = self.serial_conn.read(4)
            if not header:
                return None
            
            if header != b'IMG:':
                # Bukan data gambar, mungkin data telemetri
                print(f"[DEBUG] Data diterima (bukan gambar): {header}")
                return None
            
            # Terima ukuran file (8 bytes)
            size_data = self.serial_conn.read(8)
            if not size_data or len(size_data) < 8:
                print("[ERROR] Gagal membaca ukuran file")
                return None
            
            file_size = int(size_data.decode().strip())
            print(f"[INFO] Ukuran file: {file_size} bytes")
            
            # Terima ekstensi file (10 bytes)
            ext_data = self.serial_conn.read(10)
            if not ext_data or len(ext_data) < 10:
                print("[ERROR] Gagal membaca ekstensi file")
                return None
            
            extension = ext_data.decode().strip()
            print(f"[INFO] Ekstensi file: {extension}")
            
            # Terima data gambar
            received_data = b''
            while len(received_data) < file_size:
                remaining = file_size - len(received_data)
                chunk = self.serial_conn.read(min(4096, remaining))
                if not chunk:
                    break
                received_data += chunk
                progress = (len(received_data) / file_size) * 100
                print(f"\r[INFO] Progress: {progress:.1f}%", end='', flush=True)
            
            print()  # Newline setelah progress
            
            if len(received_data) == file_size:
                # Simpan gambar
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bt_image_{timestamp}.{extension}"
                filepath = os.path.join(self.save_folder, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(received_data)
                
                print(f"[INFO] Gambar disimpan: {filepath}")
                
                # Kirim konfirmasi ke client
                self.serial_conn.write(b"OK")
                self.serial_conn.flush()
                return filepath
            else:
                print(f"[ERROR] Data tidak lengkap: {len(received_data)}/{file_size}")
                self.serial_conn.write(b"FAIL")
                self.serial_conn.flush()
                return None
                
        except Exception as e:
            print(f"[ERROR] Gagal menerima gambar: {e}")
            return None
    
    def read_telemetry(self):
        """
        Membaca data telemetri (bukan gambar).
        Mengembalikan data string atau None jika tidak ada.
        """
        try:
            if self.serial_conn and self.serial_conn.in_waiting > 0:
                data = self.serial_conn.readline()
                if data:
                    return data.decode().strip()
        except Exception as e:
            print(f"[ERROR] Gagal membaca telemetri: {e}")
        return None
    
    def send_data(self, data):
        """Mengirim data ke perangkat Android"""
        try:
            if self.serial_conn:
                if isinstance(data, str):
                    data = data.encode()
                self.serial_conn.write(data)
                self.serial_conn.flush()
                return True
        except Exception as e:
            print(f"[ERROR] Gagal mengirim data: {e}")
        return False
    
    def close(self):
        """Menutup koneksi serial"""
        if self.serial_conn:
            try:
                self.serial_conn.close()
                self.serial_conn = None
                print("[INFO] Koneksi ditutup")
            except:
                pass
    
    def is_connected(self):
        """Cek apakah koneksi masih aktif"""
        return self.serial_conn is not None and self.serial_conn.is_open
    
    def run(self):
        """Menjalankan receiver dalam loop"""
        print("=" * 50)
        print("  BLUETOOTH IMAGE RECEIVER (SPP)")
        print("=" * 50)
        print(f"Port: {self.port}")
        print(f"Save folder: {self.save_folder}")
        print("-" * 50)
        
        try:
            while True:
                # Tunggu koneksi
                if not self.is_connected():
                    if not self.wait_for_connection():
                        time.sleep(2)
                        continue
                
                try:
                    # Cek apakah ada data
                    if self.serial_conn.in_waiting > 0:
                        # Peek header untuk menentukan tipe data
                        peek = self.serial_conn.read(4)
                        
                        if peek == b'IMG:':
                            # Data gambar - proses dengan receive_image
                            # Kembalikan header ke buffer (tidak bisa, jadi langsung proses)
                            self._process_image_after_header()
                        else:
                            # Data telemetri atau lainnya
                            remaining = self.serial_conn.readline()
                            full_data = peek + remaining
                            print(f"[TELEMETRI] {full_data.decode().strip()}")
                    else:
                        time.sleep(0.1)
                        
                except serial.SerialException as e:
                    print(f"[WARNING] Koneksi terputus: {e}")
                    self.close()
                    print("[INFO] Menunggu koneksi ulang...")
                    
        except KeyboardInterrupt:
            print("\n[INFO] Dihentikan oleh user")
        finally:
            self.close()
    
    def _process_image_after_header(self):
        """Proses gambar setelah header IMG: sudah dibaca"""
        try:
            # Terima ukuran file (8 bytes)
            size_data = self.serial_conn.read(8)
            if not size_data or len(size_data) < 8:
                print("[ERROR] Gagal membaca ukuran file")
                return None
            
            file_size = int(size_data.decode().strip())
            print(f"[INFO] Menerima gambar - Ukuran: {file_size} bytes")
            
            # Terima ekstensi file (10 bytes)
            ext_data = self.serial_conn.read(10)
            extension = ext_data.decode().strip()
            print(f"[INFO] Ekstensi: {extension}")
            
            # Terima data gambar
            received_data = b''
            while len(received_data) < file_size:
                remaining = file_size - len(received_data)
                chunk = self.serial_conn.read(min(4096, remaining))
                if not chunk:
                    break
                received_data += chunk
                progress = (len(received_data) / file_size) * 100
                print(f"\r[INFO] Progress: {progress:.1f}%", end='', flush=True)
            
            print()
            
            if len(received_data) == file_size:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bt_image_{timestamp}.{extension}"
                filepath = os.path.join(self.save_folder, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(received_data)
                
                print(f"[INFO] Gambar disimpan: {filepath}")
                self.serial_conn.write(b"OK")
                self.serial_conn.flush()
                return filepath
            else:
                print(f"[ERROR] Data tidak lengkap: {len(received_data)}/{file_size}")
                self.serial_conn.write(b"FAIL")
                self.serial_conn.flush()
                return None
                
        except Exception as e:
            print(f"[ERROR] Gagal menerima gambar: {e}")
            return None


if __name__ == "__main__":
    import sys
    
    # Default settings
    port = '/dev/rfcomm0'
    save_folder = 'received_images'
    
    # Parse arguments
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        save_folder = sys.argv[2]
    
    receiver = BluetoothImageReceiver(
        port=port,
        save_folder=save_folder
    )
    receiver.run()

