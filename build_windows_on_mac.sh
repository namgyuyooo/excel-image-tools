#!/bin/bash

# 맥에서 윈도우용 빌드를 위한 스크립트
# 이 스크립트는 Docker나 VM 없이는 완전한 크로스 빌드가 불가능합니다
# GitHub Actions 또는 Docker 사용을 권장합니다

set -e

echo "========================================="
echo "Windows Build on Mac (Limited Support)"
echo "========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

function print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function print_error() {
    echo -e "${RED}❌ $1${NC}"
}

function print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_warning "맥에서는 윈도우용 네이티브 바이너리를 직접 생성할 수 없습니다."
echo ""
echo "다음 방법들을 사용하세요:"
echo ""

print_info "1. GitHub Actions 사용 (추천)"
echo "   - GitHub 저장소에 코드를 푸시하고"
echo "   - .github/workflows/build-windows.yml 파일이 생성되었습니다"
echo "   - GitHub에서 Actions 탭으로 가서 'Build Windows Executable' 워크플로우를 실행하세요"
echo ""

print_info "2. Docker 사용"
echo "   - Docker Desktop을 설치하고"
echo "   - 다음 명령어를 실행하세요:"
echo "   docker build -f Dockerfile.windows -t excel-labeler-windows ."
echo "   docker run -v \$(pwd)/dist-windows:/app/dist excel-labeler-windows"
echo ""

print_info "3. VM 또는 실제 Windows 머신 사용"
echo "   - Parallels, VMware, 또는 실제 Windows PC에서"
echo "   - build_windows_final.bat 또는 build_windows_final.ps1 실행"
echo ""

# requirements.txt 확인
if [ -f "requirements.txt" ]; then
    print_success "requirements.txt 파일 존재 확인"
else
    print_error "requirements.txt 파일이 없습니다. 생성하는 중..."
    
    # 기본 requirements.txt 생성
    cat > requirements.txt << EOF
PySide6>=6.5.0
pandas>=2.0.0
openpyxl>=3.1.0
pillow>=10.0.0
psutil>=5.9.0
EOF
    
    print_success "requirements.txt 파일 생성됨"
fi

# PyInstaller spec 파일 생성 (Windows용)
print_info "Windows용 PyInstaller spec 파일 생성..."

cat > excel_image_labeler_windows.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['inference_labeler.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'pandas',
        'openpyxl',
        'PIL',
        'psutil'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ExcelImageLabeler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)
EOF

print_success "excel_image_labeler_windows.spec 파일 생성됨"

echo ""
print_warning "이 스크립트는 준비 작업만 수행했습니다."
print_info "실제 Windows 빌드를 위해서는 위에 제시된 방법 중 하나를 사용하세요."

# 실행 권한 부여
chmod +x "$0"