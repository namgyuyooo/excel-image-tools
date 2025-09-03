@echo off
echo ========================================
echo Excel Image Labeler - Windows EXE Builder
echo ========================================

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt
pip install pyinstaller

REM Create dist and build directories
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
mkdir dist
mkdir build

REM Build the executable
echo Building Windows executable...
pyinstaller --clean --onefile --windowed --name excel_image_labeler inference_labeler.py

REM Check if build was successful
if exist dist\excel_image_labeler.exe (
    echo.
    echo ========================================
    echo ✅ Build completed successfully!
    echo ========================================
    echo Executable created: dist\excel_image_labeler.exe
    echo.
    echo To run the application:
    echo   Double-click dist\excel_image_labeler.exe
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ❌ Build failed!
    echo ========================================
    echo Check the error messages above.
    echo ========================================
)

pause
