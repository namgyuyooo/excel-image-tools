@echo off
echo ========================================
echo Excel Image Labeler - Windows EXE Builder
echo ========================================
echo.

REM Check if we're running on Windows
ver | findstr /i "Windows" >nul
if %errorlevel% neq 0 (
    echo ❌ This script must be run on Windows!
    echo Please copy this project to a Windows machine and run this script there.
    pause
    exit /b 1
)

echo ✅ Running on Windows
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
echo ✅ Python found: %python_version%
echo.

REM Create virtual environment
echo 🏗️ Creating virtual environment...
if exist venv (
    echo Removing existing venv...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)
echo ✅ Virtual environment created
echo.

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Failed to activate virtual environment
    pause
    exit /b 1
)
echo ✅ Virtual environment activated
echo.

REM Upgrade pip
echo 📦 Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ❌ Failed to upgrade pip
    pause
    exit /b 1
)
echo ✅ Pip upgraded
echo.

REM Install requirements
echo 📚 Installing requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install requirements
    echo Check your internet connection and try again
    pause
    exit /b 1
)
echo ✅ Requirements installed
echo.

REM Install PyInstaller
echo 🔨 Installing PyInstaller...
pip install pyinstaller==6.15.0
if errorlevel 1 (
    echo ❌ Failed to install PyInstaller
    pause
    exit /b 1
)
echo ✅ PyInstaller installed
echo.

REM Install additional Windows dependencies
echo 🪟 Installing Windows-specific dependencies...
pip install pywin32
pip install pefile
echo ✅ Windows dependencies installed
echo.

REM Clean previous builds
echo 🧹 Cleaning previous builds...
if exist dist rmdir /s /q dist >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
mkdir dist 2>nul
mkdir build 2>nul
echo ✅ Previous builds cleaned
echo.

REM Build the executable
echo 🚀 Building Windows executable...
echo This may take several minutes...
echo.

pyinstaller ^
    --clean ^
    --onefile ^
    --windowed ^
    --name excel_image_labeler ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import pandas ^
    --hidden-import numpy ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import openpyxl ^
    --hidden-import psutil ^
    --hidden-import create_excel_from_seg_csv ^
    --hidden-import setup_dialog ^
    --hidden-import utils ^
    --hidden-import memory_monitor ^
    --hidden-import shiboken6 ^
    --hidden-import dateutil ^
    --hidden-import pytz ^
    --hidden-import tzdata ^
    --exclude-module tkinter ^
    --exclude-module unittest ^
    --exclude-module email ^
    --exclude-module http ^
    --exclude-module xmlrpc ^
    --exclude-module pydoc ^
    inference_labeler.py

if errorlevel 1 (
    echo.
    echo ❌ Build failed!
    echo.
    echo Common solutions:
    echo 1. Check if antivirus software is blocking PyInstaller
    echo 2. Try running as Administrator
    echo 3. Close other Python processes
    echo 4. Restart your computer and try again
    echo.
    pause
    exit /b 1
)

REM Check if build was successful
if exist "dist\excel_image_labeler.exe" (
    echo.
    echo ========================================
    echo ✅ Build completed successfully!
    echo ========================================
    echo.
    echo 📁 Executable location: %cd%\dist\excel_image_labeler.exe
    echo.

    REM Get file size
    for %%A in ("dist\excel_image_labeler.exe") do set file_size=%%~zA
    set /a file_size_mb=%file_size%/1048576
    echo 📊 File size: %file_size_mb% MB
    echo.

    echo 🎯 How to use:
    echo   1. Copy dist\excel_image_labeler.exe to any Windows computer
    echo   2. Double-click to run (no installation required)
    echo   3. For debugging, run from command prompt to see console output
    echo.

    echo 🔧 Additional notes:
    echo   - The exe file is completely self-contained
    echo   - No Python installation required on target machines
    echo   - May require Microsoft Visual C++ Redistributables on older Windows
    echo.

    echo ========================================
    echo 🎉 Excel Image Labeler Windows EXE Ready!
    echo ========================================
) else (
    echo.
    echo ❌ Build completed but exe file not found!
    echo Check the build output above for errors.
    echo.
)

echo.
echo Press any key to exit...
pause >nul
