#!/bin/bash
set -e

echo "Creating build environment..."
echo "Creating build environment..."
echo "Creating build environment..."
# Create a virtual environment to avoid PEP 668 errors
# Use --system-site-packages to allow using apt-installed PyQt5
if ! python3 -m venv build_venv --system-site-packages; then
    echo "venv module missing. Attempting to install..."
    if [ "$EUID" -eq 0 ]; then
        apt-get update && apt-get install -y python3-venv python3-pyqt5 python3-opencv || apt-get install -y python3.12-venv python3-pyqt5 python3-opencv
        python3 -m venv build_venv --system-site-packages
    else
        echo "Error: python3-venv is missing. Please run: sudo apt install python3-venv python3-pyqt5 python3-opencv"
        exit 1
    fi
fi
source build_venv/bin/activate

echo "Installing dependencies..."
# Ensure system PyQt5 and OpenCV is installed
if [ "$EUID" -eq 0 ]; then
    apt-get install -y python3-pyqt5 python3-opencv
else
    echo "Note: Ensure python3-pyqt5 and python3-opencv are installed via apt if not already present."
fi

pip install --upgrade pip
pip install pyinstaller
if [ -f "requirements.txt" ]; then
    # Exclude PyQt5 from pip install as we use the system one
    grep -v "PyQt5" requirements.txt > temp_requirements.txt
    pip install -r temp_requirements.txt
    rm temp_requirements.txt
fi

echo "Cleaning previous builds..."
rm -rf build dist *.spec

echo "Building CNS_App..."
# --add-data format for Linux is src:dest
pyinstaller --noconfirm --onefile --windowed --name "CNS_App" \
    --add-data "icon.png:." \
    --add-data "DejaVuSans.ttf:." \
    --add-data "settings.py:." \
    --hidden-import "PIL" \
    --hidden-import "reportlab" \
    --hidden-import "sqlite3" \
    --hidden-import "cv2" \
    --icon="icon.png" \
    "mainS.py"

echo "Build complete. Executable is in dist/CNS_App"

# Deactivate virtual environment
deactivate
# Optional: Remove build environment to save space
# rm -rf build_venv
