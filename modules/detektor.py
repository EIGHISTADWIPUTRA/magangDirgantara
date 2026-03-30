from ultralytics import YOLO
import cv2
import time
import os

class YoloDetektor:
	def __init__(self, path):
		# Path wajib diisi misalkan 'ncnn_model'
		try:
			# Validasi path model
			if not os.path.exists(path):
				raise FileNotFoundError(f"[x] Path model tidak ditemukan: {path}")
			
			# Load model YOLO
			self.model = YOLO(path, task='detect')
			self.kelas = self.model.names  # mengambil daftar nama kelas
			self.p_time = time.time()
			print('[V] Model berhasil dimuat')
		except FileNotFoundError as e:
			print(f"[x] Error: {e}")
			raise
		except Exception as e:
			print(f"[x] Gagal memuat model: {e}")
			raise RuntimeError(f"Tidak dapat memuat model YOLO dari {path}") from e
		
	def prediksi(self, frame):
		# Validasi input frame
		if frame is None or frame.size == 0:
			print("[!] Warning: Frame kosong diterima di prediksi")
			return []
		
		try:
			return self.model(frame, stream=True, verbose=False)
		except Exception as e:
			print(f"[!] Error prediksi model: {e}")
			return []
		
	def bounding_box(self, frame, hasil, blue=0, green=255, red=0, tebal=2):
		# Validasi input frame
		if frame is None or frame.size == 0:
			print("[!] Warning: Frame kosong diterima di bounding_box")
			return frame
		
		# Validasi parameter warna (0-255)
		blue = max(0, min(255, blue))
		green = max(0, min(255, green))
		red = max(0, min(255, red))
		
		try:
			for label in hasil:
				box = label.boxes
				
				for koordinat in box:
					try:
						# Ambil koordinat (x1, y1, x2, y2)
						x1, y1, x2, y2 = koordinat.xyxy[0]  # ambil koordinat. bentuknya masih float
						x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)  # Type casting ke int
						
						# Ambil Confident Score dan ID Kelas
						conf = float(koordinat.conf[0])
						id_kelas = int(koordinat.cls[0])
						label = f"{self.kelas[id_kelas]} {conf:.2f}"  # Label berisi nama kelas dan confident score nya
						
						# Gambar Bounding Box
						cv2.rectangle(frame, (x1, y1), (x2, y2), (blue, green, red), tebal)
						
						# Gambar label
						cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (blue, green, red), 2)
					except (IndexError, AttributeError, KeyError) as e:
						print(f"[!] Warning: Deteksi invalid diabaikan - {e}")
						continue
		except Exception as e:
			print(f"[!] Error saat menggambar bounding box: {e}")
		
		return frame
		
	def fps(self, frame):
		# Logika Hitung FPS
		c_time = time.time()
		selisih = c_time - self.p_time
		
		if selisih > 0:
			fps = 1 / selisih
		else :
			fps = 0
			
		self.p_time = c_time # Update waktu sebelumnya
		
		# Gambar ke Frame
		lebar = frame.shape[1]
		cv2.putText(frame, f"FPS: {int(fps)}", (lebar - 120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
		return frame
	
	def target_terdeteksi(self, hasil, target):
		"""
		Cek apakah target terdeteksi dalam hasil deteksi
		
		Parameter:
			hasil: Hasil deteksi dari method prediksi()
			target: Nama objek yang dicari (contoh: 'person', 'car', 'bottle')
		
		Return:
			True jika target ditemukan, False jika tidak
		"""
		try:
			# Loop setiap hasil deteksi
			for label in hasil:
				box = label.boxes
				
				for koordinat in box:
					try:
						# Ambil ID kelas yang terdeteksi
						id_kelas = int(koordinat.cls[0])
						nama_kelas = self.kelas[id_kelas]
						
						# Cek apakah nama kelas cocok dengan target (case-insensitive)
						if nama_kelas.lower() == target.lower():
							return True
					except (IndexError, AttributeError, KeyError) as e:
						print(f"[!] Warning: Error saat cek target - {e}")
						continue
			
			# Target tidak ditemukan
			return False
		except Exception as e:
			print(f"[!] Error saat mengecek target: {e}")
			return False
