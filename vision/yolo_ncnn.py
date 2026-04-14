from ultralytics import YOLO

# 1. Tentukan nama model yang ingin di-download
# 'yolov8n.pt' adalah versi Nano (paling ringan & cepat untuk Raspberry Pi)
model_name = '/home/eighista/Documents/MAGANG/finalCode/models/yolo.pt'

print(f"Sedang mengunduh model {model_name}...")
model = YOLO(model_name)

# 2. Export model ke format NCNN
# half=True: Menggunakan FP16 (menghemat memori & mempercepat di CPU Pi)
# imgsz=640: Resolusi standar (bisa kamu ubah jika perlu)
print("Sedang memulai proses export ke NCNN... Mohon tunggu.")
path_hasil = model.export(format='ncnn', half = True, imgsz=416)

print("-" * 30)
print(f"BERHASIL! Model NCNN kamu tersimpan di: {path_hasil}")
print("Kamu bisa menggunakan folder tersebut untuk 'path' di YoloDetektor kamu.")
