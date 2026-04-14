"""
Socket.IO image receiver server for Raspberry Pi.

This server receives image payloads from a client (for example GCS on laptop)
and saves them into the local `received_images` folder.

Features:
- Socket.IO connection with token authentication
- Accepts image payload as base64 string or binary bytes
- Safe filename handling with extension whitelist
- Saves files in finalCode/server/received_images

Environment variables (optional):
- TARGET_SOCKET_TOKEN: auth token (default: token-gcs-rudal-2026)
- SOCKET_SERVER_HOST: bind host (default: 0.0.0.0)
- SOCKET_SERVER_PORT: bind port (default: 5001)

Run:
    python -m finalCode.server.socket_server
or:
    python finalCode/server/socket_server.py
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any, Dict, Tuple

from dotenv import load_dotenv
from flask import Flask, request
from flask_socketio import SocketIO, disconnect
from werkzeug.utils import secure_filename


load_dotenv()

HOST = os.getenv("SOCKET_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("SOCKET_SERVER_PORT", "5001"))
AUTH_TOKEN = os.getenv("TARGET_SOCKET_TOKEN", "token-gcs-rudal-2026")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "gif"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "received_images")
os.makedirs(SAVE_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "rudal-secret")
socketio = SocketIO(app, cors_allowed_origins="*")


def _is_allowed_extension(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _normalize_filename(filename: str | None) -> str:
    if not filename:
        return f"target_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"

    safe_name = secure_filename(filename)
    if not safe_name or not _is_allowed_extension(safe_name):
        return f"target_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    return safe_name


def _decode_image_payload(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Decode payload into raw image bytes and normalized filename.

    Supported payload formats:
    1. {"filename": "a.jpg", "image_base64": "..."}
    2. {"filename": "a.jpg", "image_base64": "data:image/jpeg;base64,..."}
    3. {"filename": "a.jpg", "image_bytes": <bytes|bytearray|list[int]>}
    """
    filename = _normalize_filename(data.get("filename"))

    if "image_base64" in data:
        encoded = data.get("image_base64")
        if not isinstance(encoded, str) or not encoded.strip():
            raise ValueError("Field 'image_base64' must be a non-empty string")

        if "," in encoded and encoded.strip().startswith("data:"):
            encoded = encoded.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("Invalid base64 image payload") from exc

        if not image_bytes:
            raise ValueError("Decoded image is empty")
        return image_bytes, filename

    if "image_bytes" in data:
        raw = data.get("image_bytes")
        if isinstance(raw, (bytes, bytearray)):
            image_bytes = bytes(raw)
        elif isinstance(raw, list):
            image_bytes = bytes(raw)
        else:
            raise ValueError("Field 'image_bytes' must be bytes, bytearray, or list[int]")

        if not image_bytes:
            raise ValueError("Image bytes are empty")
        return image_bytes, filename

    raise ValueError("Payload must contain 'image_base64' or 'image_bytes'")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "socket-image-server"}


@socketio.on("connect")
def on_connect(auth: Dict[str, Any] | None) -> bool:
    token = None
    if isinstance(auth, dict):
        token = auth.get("token")

    # Allow fallback from query string: ?token=...
    if not token:
        token = request.args.get("token")

    if isinstance(token, str) and token.startswith("token="):
        token = token.split("=", 1)[1]

    if token != AUTH_TOKEN:
        print("[WARN] Rejected socket connection: invalid token")
        disconnect()
        return False

    print("[INFO] Client connected")
    return True


@socketio.on("disconnect")
def on_disconnect() -> None:
    print("[INFO] Client disconnected")


@socketio.on("upload_image")
def on_upload_image(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")

        image_bytes, filename = _decode_image_payload(payload)
        save_path = os.path.join(SAVE_DIR, filename)

        with open(save_path, "wb") as image_file:
            image_file.write(image_bytes)

        print(f"[INFO] Image saved: {save_path}")
        return {
            "ok": True,
            "message": "Image received",
            "filename": filename,
            "path": save_path,
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


@socketio.on("upload_target")
def on_upload_target(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Alias event name for compatibility with older clients.
    return on_upload_image(payload)


def main() -> None:
    print("=" * 56)
    print("  SOCKET.IO IMAGE RECEIVER SERVER")
    print("=" * 56)
    print(f"Host           : {HOST}")
    print(f"Port           : {PORT}")
    print(f"Save folder    : {SAVE_DIR}")
    print(f"Allowed format : {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    print("-" * 56)
    socketio.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
