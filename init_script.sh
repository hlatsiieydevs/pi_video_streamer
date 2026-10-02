#!/bin/bash

# Exit on error
set -e

echo "=========================================================="
echo "  BASIC VIDEO STREAMER: Initialization Script             "
echo "=========================================================="

# 1. Update and install system dependencies
echo "[+] Installing system dependencies (requires sudo)..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nodejs npm ffmpeg libsm6 libxext6 libgl1

# 2. Set up Python virtual environment
echo "[+] Setting up Python virtual environment..."
# Ensure we operate within the app directory
cd "$(dirname "$0")/app" || exit 1

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[+] Virtual environment created."
else
    echo "[*] Virtual environment already exists."
fi

# 3. Install Python requirements
echo "[+] Installing Python dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 4. Install Node.js dependencies
echo "[+] Installing Node.js dependencies..."
npm install

# 5. Testing the installation
echo "=========================================================="
echo "[+] Running post-installation tests..."

# Test Python imports
echo "[*] Testing Python environment..."
if ./venv/bin/python -c "import flask; import cv2; import numpy" 2>/dev/null; then
    echo "  - Python imports successful (Flask, OpenCV, Numpy)!"
else
    echo "  [!] Error: Failed to import Python libraries."
    exit 1
fi

# Test Node.js
echo "[*] Testing Node.js environment..."
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    echo "  - Node.js $(node -v) is installed."
    echo "  - npm $(npm -v) is installed."
else
    echo "  [!] Error: Node.js or npm is missing."
    exit 1
fi

echo "=========================================================="
echo "[+] Initialization complete! Everything works as expected."
echo "    You can now start the streamer using:"
echo "    cd .. && ./start.sh"
echo "=========================================================="
