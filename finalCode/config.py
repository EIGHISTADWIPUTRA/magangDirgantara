"""Central configuration for finalCode package.

All shared constants are defined here. Hardware-specific imports (like SX127x
constants) are stored as raw values to allow importing config.py anywhere.
"""

# ─── Camera ──────────────────────────────────────────────────────────────────
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# ─── ORB Feature Matching ────────────────────────────────────────────────────
ORB_NFEATURES = 1500
ORB_RATIO_THRESHOLD = 0.7
MIN_GOOD_MATCHES = 10
MAX_DRAW_MATCHES = 30

# ─── FLANN (LSH for binary descriptors) ──────────────────────────────────────
FLANN_TABLE_NUMBER = 6
FLANN_KEY_SIZE = 12
FLANN_MULTI_PROBE_LEVEL = 1
FLANN_CHECKS = 50
FLANN_ALGORITHM_LSH = 6  # LSH algorithm index for binary descriptors

# ─── LoRa Radio ──────────────────────────────────────────────────────────────
# Frequency in MHz
LORA_FREQUENCY = 433.0

# Sync word (raw hex value) - must match ESP32 receiver (0x12)
LORA_SYNC_WORD = 0x12

# Spreading factor (7-12)
LORA_SPREADING_FACTOR = 7

# Bandwidth (raw value, apply using SX127x BW constants at runtime)
# BW.BW250 = 8 (250kHz) - must match ESP32 receiver setSignalBandwidth(250E3)
LORA_BANDWIDTH_RAW = 0x08

# Coding rate (raw value, apply using SX127x CODING_RATE constants at runtime)
# CODING_RATE.CR4_5 = 0x01
LORA_CODING_RATE_RAW = 0x01

# ─── Server ──────────────────────────────────────────────────────────────────
WIFI_SERVER_HOST = '0.0.0.0'
WIFI_SERVER_PORT = 5006
BLUETOOTH_PORT = '/dev/rfcomm0'
BLUETOOTH_BAUDRATE = 115200

# ─── Paths ───────────────────────────────────────────────────────────────────
RECEIVED_IMAGES_DIR = 'received_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp')

# ─── Sensor ──────────────────────────────────────────────────────────────────
BMP280_I2C_ADDRESS = 0x76
MPU6050_I2C_ADDRESS = 0x68
GY511_I2C_ADDRESS_ACCEL = 0x19  # Default accelerometer address (alternative: 0x18)
GY511_I2C_ADDRESS_MAG = 0x1D    # Magnetometer address (detected on your module at 0x1d)
SEA_LEVEL_PRESSURE = 1013.25  # hPa
