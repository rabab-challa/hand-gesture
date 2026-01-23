# run_setup.ps1 - run from project folder
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

# Activate virtualenv for this script session
& ".\.venv\Scripts\Activate.ps1"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r .\requirements.txt

Write-Host "Checking OpenCV version..."
python -c "import cv2; print('opencv', cv2.__version__)"

Write-Host "Checking MediaPipe version..."
python -c "import mediapipe as mp; print('mediapipe', mp.__version__)"

Write-Host "Running camera test..."
python .\test_camera.py

Write-Host "If camera opened, starting the app..."
python .\main.py
