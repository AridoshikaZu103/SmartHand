Write-Host "Cleaning up old build..."
if (Test-Path "dist\main.exe") {
    Remove-Item -Force "dist\main.exe"
    Write-Host "Deleted old main.exe"
}

Write-Host "Rebuilding main.exe using PyInstaller..."
pyinstaller --onefile --noconsole --collect-all mediapipe --add-data "hand_landmarker.task;." main.py

Write-Host "Build complete! You can find the new executable in the 'dist' folder."
