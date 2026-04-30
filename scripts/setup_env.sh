#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/setup_env.sh [--no-apt] [--no-hw] [--venv=PATH]

Options:
  --no-apt     Skip installing system packages via apt.
  --no-hw      Skip hardware-specific packages (RPi.GPIO, spidev).
  --venv=PATH  Override virtualenv path (default: .venv in repo root).
EOF
}

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/.venv}"
WITH_APT=1
WITH_HW=1

for arg in "$@"; do
  case "$arg" in
    --no-apt) WITH_APT=0 ;;
    --no-hw) WITH_HW=0 ;;
    --venv=*) VENV_DIR="${arg#*=}" ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown arg: $arg"
      usage
      exit 1
      ;;
  esac
done

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3 first." >&2
  exit 1
fi

if [[ $WITH_APT -eq 1 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing system packages (apt)..."
    sudo apt-get update
    sudo apt-get install -y python3-venv python3-dev python3-pip python3-tk build-essential
    if [[ $WITH_HW -eq 1 ]]; then
      sudo apt-get install -y i2c-tools python3-spidev || true
    fi
  else
    echo "apt-get not found, skipping system packages."
  fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel

REQ_FILE="$PROJECT_ROOT/kebutuhan.txt"
if [[ -f "$REQ_FILE" ]]; then
  python -m pip install -r "$REQ_FILE"
fi

python -m pip install numpy flask werkzeug flask_socketio python-dotenv psutil pillow pyserial lsm303d \
  adafruit-blinka adafruit-circuitpython-bmp280 adafruit-circuitpython-mpu6050

if [[ $WITH_HW -eq 1 ]]; then
  python -m pip install RPi.GPIO spidev || echo "WARN: Failed to install RPi.GPIO/spidev (non-RPi?)."
fi

if [[ -d "$PROJECT_ROOT/pySX127x" ]]; then
  python -m pip install -e "$PROJECT_ROOT/pySX127x"
fi

echo "Done."
echo "Activate with: source \"$VENV_DIR/bin/activate\""
