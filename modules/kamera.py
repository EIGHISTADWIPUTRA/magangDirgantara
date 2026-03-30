import cv2

class WebcamStream:
	def __init__(self, sumber=0, lebar=640, tinggi=320):
		# Validasi parameter sumber
		if not isinstance(sumber, (int, str)):
			raise ValueError(f"[x] Sumber kamera harus integer atau string, bukan {type(sumber)}")
		
		try:
			# Inisialisasi kamera
			self.stream = cv2.VideoCapture(sumber)  # Sumber kamera default adalah 0
			
			# Mengatur ukuran frame
			self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, lebar)
			self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, tinggi)
			
			# Cek apakah terdapat kamera yang terpasang
			if not self.stream.isOpened():
				print("[x] Tidak ada kamera yang ditemukan")
				raise RuntimeError(f"Gagal membuka kamera dari sumber: {sumber}")
		except cv2.error as e:
			print(f"[x] Error OpenCV saat inisialisasi kamera: {e}")
			raise
		except Exception as e:
			print(f"[x] Error tidak terduga saat inisialisasi kamera: {e}")
			raise
	
	def siap(self):
		return self.stream.isOpened()
			
	def get_frame(self):
		#Mengambil frame terbaru
		ret, frame = self.stream.read() #ret mengecek apakah pengambilan gambar berhasil, nilaiya true/false (boolean)
										#frame menyimpan data pixel gambar, tipe datanya numpy array (matriks)
		return ret, frame
		
	def berhenti(self):
		# Kamera berhenti
		try:
			if self.stream is not None:
				self.stream.release()
		except Exception as e:
			print(f"[!] Warning: Error saat menutup kamera - {e}")
	
	# Context manager methods untuk automatic resource management
	def __enter__(self):
		return self
	
	def __exit__(self, exc_type, exc_val, exc_tb):
		self.berhenti()
		return False  # Don't suppress exceptions
		
