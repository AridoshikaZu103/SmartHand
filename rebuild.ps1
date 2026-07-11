# ==============================================================================
# SmartHand - Executable Build Script
# ==============================================================================
# This script uses PyInstaller to compile the python source code into a standalone
# Windows executable (.exe). It automatically bundles the MediaPipe AI models
# and required dependencies so the end-user doesn't need to install Python.
#
# Requirements: pip install pyinstaller

Write-Host "Cleaning up old build..."
if (Test-Path "dist\main.exe") {
    Remove-Item -Force "dist\main.exe"
    Write-Host "Deleted old main.exe"
}

Write-Host "Rebuilding main.exe using PyInstaller..."
pyinstaller --onefile --noconsole --collect-all mediapipe --add-data "hand_landmarker.task;." main.py

Write-Host "Build complete! You can find the new executable in the 'dist' folder."
