from modules.kamera import WebcamStream
from modules.detektor import YoloDetektor
import cv2
import sys

def init_sistem():
	"""Inisialisasi kamera dan detektor dengan error handling"""
	try:
		print("[*] Menginisialisasi kamera...")
		kamera = WebcamStream(0, 640, 480)
		print("[V] Kamera berhasil diinisialisasi")
		
		print("[*] Memuat model YOLO...")
		detektor = YoloDetektor('models/aircraft_ncnn_model')
		
		return kamera, detektor
	except FileNotFoundError as e:
		print(f"[x] Error: File tidak ditemukan - {e}")
		print("[!] Pastikan model YOLO tersedia di path yang benar")
		return None, None
	except RuntimeError as e:
		print(f"[x] Error Runtime: {e}")
		print("[!] Pastikan kamera terhubung dengan benar")
		return None, None
	except Exception as e:
		print(f"[x] Error tidak terduga saat inisialisasi: {e}")
		return None, None

def jalankan_deteksi(kamera, detektor):
	"""Menjalankan loop deteksi objek real-time"""
	print("====================================================")
	print("= SELAMAT DATANG DI SIMULASI RUDAL COMPUTER VISION =")
	print("====================================================")
	print("[*] Tekan 'q' untuk keluar")
	print()
	
	try:
		while True:
			try:
				terhubung, frame = kamera.get_frame()
				
				if not terhubung:
					print("[x] Tidak ada kamera yang terdeteksi")
					break
				
				#hasil = detektor.prediksi(frame)
				#hasil = list(hasil)
				
				frame = detektor.fps(frame)
				
				cv2.imshow("Stream", frame)
				
				if cv2.waitKey(1) == ord('q'):
					print("[*] Keluar dari program...")
					break
					
			except KeyboardInterrupt:
				print("\n[*] Program dihentikan oleh user")
				break
			except cv2.error as e:
				print(f"[!] Error OpenCV: {e}")
				continue  # Coba lanjutkan untuk error non-critical
			except Exception as e:
				print(f"[!] Error dalam loop deteksi: {e}")
				continue  # Coba lanjutkan untuk error non-critical
	except KeyboardInterrupt:
		print("\n[*] Program dihentikan oleh user")

def cleanup_resources(kamera):
	"""Membersihkan semua resources (kamera, windows)"""
	try:
		if kamera is not None:
			kamera.berhenti()
			print("[V] Kamera berhasil dimatikan")
	except Exception as e:
		print(f"[!] Warning: Error saat cleanup kamera - {e}")
	
	try:
		cv2.destroyAllWindows()
		print("[V] Window ditutup")
	except Exception as e:
		print(f"[!] Warning: Error saat menutup windows - {e}")

def main():
	"""Fungsi utama program"""
	kamera = None
	detektor = None
	
	try:
		# Inisialisasi sistem
		kamera, detektor = init_sistem()
		
		if kamera is None or detektor is None:
			print("[!] Inisialisasi gagal. Program dihentikan.")
			sys.exit(1)
		
		if not kamera.siap():
			print("[!] Mohon cek ketersediaan kamera")
			sys.exit(1)
		
		# Jalankan deteksi
		jalankan_deteksi(kamera, detektor)
		
	finally:
		# Pastikan cleanup selalu dijalankan
		cleanup_resources(kamera)

if __name__ == "__main__":
	main()
