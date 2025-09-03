
@echo off
echo Building Excel Image Labeler for Windows...

REM Quick and simple build
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name excel_image_labeler inference_labeler.py

echo.
if exist "dist\excel_image_labeler.exe" (
    echo ✅ Success! Find your exe at: dist\excel_image_labeler.exe
) else (
    echo ❌ Build failed. Check the errors above.
)
echo.
pause
