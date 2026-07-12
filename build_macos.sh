#!/bin/bash

# ==============================================================================
# SmartHand macOS Build Script (PyInstaller)
# Converts main_macos.py into a standalone macOS application
# ==============================================================================

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     SmartHand macOS Build Script (PyInstaller)                ║"
echo "║     Creating standalone executable for macOS...               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python3 is not installed!"
    echo "   Please install Python from: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"
echo ""

# Check if we're in the SmartHand directory
if [ ! -f "main_macos.py" ]; then
    echo "❌ ERROR: main_macos.py not found!"
    echo "   Please run this script from the SmartHand directory"
    exit 1
fi

if [ ! -f "hand_landmarker.task" ]; then
    echo "❌ ERROR: hand_landmarker.task not found!"
    echo "   Please ensure the AI model file exists in this directory"
    exit 1
fi

echo "✓ Found main_macos.py"
echo "✓ Found hand_landmarker.task"
echo ""

# Install/upgrade PyInstaller
echo "📦 Installing PyInstaller..."
pip3 install --upgrade pyinstaller

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to install PyInstaller"
    exit 1
fi

echo "✓ PyInstaller installed successfully"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous build artifacts..."
rm -rf build dist main_macos.spec __pycache__
echo "✓ Cleaned previous builds"
echo ""

# Build the executable
echo "🔨 Building executable (this may take 5-10 minutes)..."
echo "   Please wait, bundling AI models..."
echo ""

pyinstaller \
    --name=SmartHand \
    --windowed \
    --onefile \
    --icon=None \
    --add-data "hand_landmarker.task:." \
    --hidden-import=mediapipe \
    --hidden-import=cv2 \
    --hidden-import=numpy \
    --hidden-import=pynput \
    --hidden-import=psutil \
    main_macos.py

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Build failed!"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     ✅ BUILD SUCCESSFUL!                                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Output location:"
echo "   dist/SmartHand"
echo ""
echo "🚀 To run the app:"
echo "   ./dist/SmartHand"
echo ""
echo "Or double-click: dist/SmartHand"
echo ""
echo "⚠️  First launch may take 10-20 seconds (loading AI models)"
echo ""
