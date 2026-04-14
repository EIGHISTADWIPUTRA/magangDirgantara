"""
WiFi/HTTP Image Receiver Server.

This module provides a Flask-based HTTP server for receiving target images
over WiFi network. It exposes a POST endpoint at /upload_target that accepts
image file uploads.

Features:
- Supports multiple image formats: PNG, JPG, JPEG, GIF, BMP
- Secure filename handling to prevent path traversal attacks
- Auto-creates the upload folder if it doesn't exist
- Returns appropriate status codes and messages

Usage:
    python wifi_server.py

Configuration:
    - Host: 0.0.0.0 (accessible from any network interface)
    - Port: 5006
    - Upload folder: received_images/

Dependencies:
    pip install flask werkzeug
"""

import os
from flask import Flask, request
from werkzeug.utils import secure_filename

# Flask application instance
app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'received_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename: str) -> bool:
    """
    Check if a filename has an allowed extension.

    Args:
        filename: The name of the file to check.

    Returns:
        True if the file extension is allowed, False otherwise.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_target', methods=['POST'])
def upload_file():
    """
    Handle POST requests for image uploads.

    Expects a multipart/form-data request with an 'image' field containing
    the file to upload.

    Returns:
        tuple: A message string and HTTP status code.
            - 200: File uploaded successfully
            - 400: Bad request (no file, empty filename, or invalid extension)
    """
    # Check if file is in request
    if 'image' not in request.files:
        return "No file sent", 400

    file = request.files['image']

    # Check if filename is empty
    if file.filename == '':
        return "No filename selected", 400

    # Validate and save file
    if file and allowed_file(file.filename):
        # Sanitize filename to prevent path traversal attacks
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)

        print(f"--- [INFO] File received: {filename} at {save_path} ---")
        return f"File {filename} successfully received!", 200
    else:
        return "File format not allowed", 400


if __name__ == '__main__':
    print("=" * 50)
    print("  WIFI/HTTP IMAGE RECEIVER SERVER")
    print("=" * 50)
    print(f"Host: 0.0.0.0")
    print(f"Port: 5006")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}")
    print("-" * 50)
    app.run(host='0.0.0.0', port=5006)
