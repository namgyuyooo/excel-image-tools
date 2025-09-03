param(
    [switch]$Clean,
    [switch]$Debug,
    [switch]$NoOneFile,
    [switch]$Force
)

# Requires -RunAsAdministrator if needed
#Requires -Version 5.1

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Message)
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ️ $Message" -ForegroundColor Yellow
}

Write-Header "Excel Image Labeler - Windows EXE Builder"

# Check Windows
if ($env:OS -notlike "*Windows*") {
    Write-Error "This script must be run on Windows!"
    Write-Info "Please copy this project to a Windows machine and run this script there."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Success "Running on Windows"

# Check Python
try {
    $pythonVersion = python --version 2>$null
    Write-Success "Python found: $pythonVersion"
} catch {
    Write-Error "Python is not installed or not in PATH"
    Write-Info "Please install Python 3.8+ from https://python.org"
    Write-Info "Make sure to check 'Add Python to PATH' during installation"
    Read-Host "Press Enter to exit"
    exit 1
}

# Clean if requested
if ($Clean -or $Force) {
    Write-Info "Cleaning previous builds..."
    if (Test-Path "venv") { Remove-Item "venv" -Recurse -Force }
    if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
    if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
    Write-Success "Previous builds cleaned"
}

# Create virtual environment
Write-Info "Creating virtual environment..."
if (!(Test-Path "venv")) {
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment"
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Success "Virtual environment created"
} else {
    Write-Info "Virtual environment already exists"
}

# Activate virtual environment
Write-Info "Activating virtual environment..."
& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to activate virtual environment"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Success "Virtual environment activated"

# Upgrade pip
Write-Info "Upgrading pip..."
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to upgrade pip"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Success "Pip upgraded"

# Install requirements
Write-Info "Installing requirements..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install requirements"
    Write-Info "Check your internet connection and try again"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Success "Requirements installed"

# Install PyInstaller
Write-Info "Installing PyInstaller..."
pip install pyinstaller==6.15.0
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install PyInstaller"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Success "PyInstaller installed"

# Install Windows dependencies
Write-Info "Installing Windows-specific dependencies..."
pip install pywin32 pefile
Write-Success "Windows dependencies installed"

# Create output directories
New-Item -ItemType Directory -Force -Path "dist", "build" | Out-Null

# Build arguments
$pyinstallerArgs = @("--clean", "--name", "excel_image_labeler")

if (!$NoOneFile) {
    $pyinstallerArgs += "--onefile"
}

if (!$Debug) {
    $pyinstallerArgs += "--windowed"
}

# Add hidden imports
$hiddenImports = @(
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "pandas",
    "numpy",
    "PIL",
    "PIL.Image",
    "openpyxl",
    "psutil",
    "create_excel_from_seg_csv",
    "setup_dialog",
    "utils",
    "memory_monitor",
    "shiboken6",
    "dateutil",
    "pytz",
    "tzdata"
)

foreach ($import in $hiddenImports) {
    $pyinstallerArgs += "--hidden-import", $import
}

# Add exclusions
$exclusions = @(
    "tkinter",
    "unittest",
    "email",
    "http",
    "xmlrpc",
    "pydoc"
)

foreach ($exclude in $exclusions) {
    $pyinstallerArgs += "--exclude-module", $exclude
}

$pyinstallerArgs += "inference_labeler.py"

# Build the executable
Write-Info "Building Windows executable..."
Write-Info "This may take several minutes..."
Write-Host "Command: pyinstaller $($pyinstallerArgs -join ' ')" -ForegroundColor Gray
Write-Host ""

& pyinstaller $pyinstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Error "Build failed!"
    Write-Host ""
    Write-Info "Common solutions:"
    Write-Host "1. Check if antivirus software is blocking PyInstaller" -ForegroundColor White
    Write-Host "2. Try running as Administrator" -ForegroundColor White
    Write-Host "3. Close other Python processes" -ForegroundColor White
    Write-Host "4. Restart your computer and try again" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if build was successful
if (Test-Path "dist\excel_image_labeler.exe") {
    Write-Host ""
    Write-Header "Build completed successfully!"

    # Get file size
    $fileSize = (Get-Item "dist\excel_image_labeler.exe").Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Success "Executable created: dist\excel_image_labeler.exe"
    Write-Info "File size: $fileSizeMB MB"

    Write-Host ""
    Write-Info "How to use:"
    Write-Host "  1. Copy dist\excel_image_labeler.exe to any Windows computer" -ForegroundColor White
    Write-Host "  2. Double-click to run (no installation required)" -ForegroundColor White
    Write-Host "  3. For debugging, run from command prompt to see console output" -ForegroundColor White

    Write-Host ""
    Write-Info "Additional notes:"
    Write-Host "  - The exe file is completely self-contained" -ForegroundColor White
    Write-Host "  - No Python installation required on target machines" -ForegroundColor White
    Write-Host "  - May require Microsoft Visual C++ Redistributables on older Windows" -ForegroundColor White

    Write-Host ""
    Write-Header "Excel Image Labeler Windows EXE Ready!"

} else {
    Write-Host ""
    Write-Error "Build completed but exe file not found!"
    Write-Info "Check the build output above for errors."
    Write-Host ""
}

Read-Host "Press Enter to exit"
