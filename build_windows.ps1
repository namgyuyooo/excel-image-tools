param(
    [switch]$Clean,
    [switch]$Debug,
    [switch]$NoOneFile
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Excel Image Labeler - Windows EXE Builder" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Clean previous builds
if ($Clean) {
    Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
    if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
}

# Create virtual environment if it doesn't exist
if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Install requirements
Write-Host "Installing requirements..." -ForegroundColor Yellow
pip install -r requirements.txt
pip install pyinstaller

# Build arguments
$pyinstallerArgs = @("--clean", "--name", "excel_image_labeler")

if (!$NoOneFile) {
    $pyinstallerArgs += "--onefile"
}

if (!$Debug) {
    $pyinstallerArgs += "--windowed"
}

$pyinstallerArgs += "inference_labeler.py"

# Build the executable
Write-Host "Building Windows executable..." -ForegroundColor Green
Write-Host "Command: pyinstaller $($pyinstallerArgs -join ' ')" -ForegroundColor Gray

& pyinstaller $pyinstallerArgs

# Check if build was successful
if (Test-Path "dist\excel_image_labeler.exe") {
    $fileSize = (Get-Item "dist\excel_image_labeler.exe").Length / 1MB
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✅ Build completed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Executable created: dist\excel_image_labeler.exe" -ForegroundColor White
    Write-Host "File size: $([math]::Round($fileSize, 2)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "To run the application:" -ForegroundColor Cyan
    Write-Host "  Double-click dist\excel_image_labeler.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "For debugging, run with console:" -ForegroundColor Yellow
    Write-Host "  dist\excel_image_labeler.exe" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "❌ Build failed!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Check the error messages above." -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
}
