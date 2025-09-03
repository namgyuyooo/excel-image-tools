@echo off
echo ========================================
echo Excel Image Labeler - Advanced Windows Build
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
if exist venv rmdir /s /q venv
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt
pip install pyinstaller==6.15.0

REM Install additional dependencies for Windows
pip install pywin32
pip install pefile

REM Clean previous builds
echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Create output directories
mkdir dist 2>nul
mkdir build 2>nul

REM Build with advanced options
echo Building Windows executable with advanced options...
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
    --upx-dir "" ^
    inference_labeler.py

REM Check if build was successful
if exist dist\excel_image_labeler.exe (
    echo.
    echo ========================================
    echo ✅ Advanced build completed successfully!
    echo ========================================
    for %%A in (dist\excel_image_labeler.exe) do echo File size: %%~zA bytes
    echo.
    echo Executable location: %cd%\dist\excel_image_labeler.exe
    echo.
    echo To test the executable:
    echo   1. Double-click the exe file
    echo   2. Or run: dist\excel_image_labeler.exe
    echo.
    echo Troubleshooting:
    echo   - If you get missing DLL errors, install Microsoft Visual C++ Redistributable
    echo   - For console output (debugging): dist\excel_image_labeler.exe --debug
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ❌ Build failed!
    echo ========================================
    echo Common issues:
    echo   1. Check if all dependencies are installed
    echo   2. Try running as Administrator
    echo   3. Check antivirus software (may block PyInstaller)
    echo   4. Ensure Python is in PATH
    echo ========================================
)

echo Press any key to exit...
pause >nul
