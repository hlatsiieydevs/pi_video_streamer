#!/bin/bash
# Basic Video Streamer - Startup Script

export PATH="/home/tkdev/.local/node/bin:$PATH font"
export PATH="/home/tkdev/.local/node/bin:$PATH"

echo "=========================================================="
echo "  BASIC VIDEO STREAMER: RPi IP Camera Emulation Service   "
echo "=========================================================="

# Navigate to app directory
cd "$(dirname "$0")/app" || exit 1

PYTHON_BIN="./venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

# Step 1: Camera Hardware Connection Probe Check
echo "[+] Probing connected camera hardware..."
$PYTHON_BIN check_cameras.py
PROBE_EXIT_CODE=$?

if [ $PROBE_EXIT_CODE -ne 0 ]; then
    echo "[!] Startup aborted due to camera detection failure."
    exit 1
fi

if [ ! -d "node_modules" ]; then
    echo "[+] Installing Node dependencies..."
    npm install
fi

if [ ! -d "dist" ]; then
    echo "[+] Building Vue 3 + Vite + Tailwind CSS bundle..."
    npm run build
fi

echo "[+] Starting Flask API & RTSP Server on http://0.0.0.0:5000..."
$PYTHON_BIN app.py
