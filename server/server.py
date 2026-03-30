from flask import Flask, request
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Folder tempat menyimpan gambar yang diterima
UPLOAD_FOLDER = 'received_images'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Daftar ekstensi yang diizinkan (opsional, untuk keamanan)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_target', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return "Tidak ada file yang dikirim", 400
    
    file = request.files['image']
    
    if file.filename == '':
        return "Nama file tidak terpilih", 400

    if file and allowed_file(file.filename):
        # secure_filename membersihkan nama file dari karakter berbahaya
        filename = secure_filename(file.filename)
        
        # Opsi 1: Simpan dengan nama asli yang dikirim laptop
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Opsi 2: Jika ingin nama tetap "target_diterima" tapi ekstensi dinamis:
        # ekstensi = filename.rsplit('.', 1)[1].lower()
        # save_path = os.path.join(UPLOAD_FOLDER, f"target_diterima.{ekstensi}")

        file.save(save_path)
        
        print(f"--- [INFO] File baru diterima: {filename} di {save_path} ---")
        return f"File {filename} berhasil diterima oleh Raspberry Pi!", 200
    else:
        return "Format file tidak diizinkan", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5006)
