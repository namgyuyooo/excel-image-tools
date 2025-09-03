# Excel Image Labeler - Windows EXE 빌드 가이드

## 📋 요구사항

### 필수 소프트웨어
- **Python 3.8 이상** (https://python.org 에서 다운로드)
- **Windows 10/11**
- **Git** (선택사항, 소스코드 다운로드용)

### 시스템 요구사항
- **RAM**: 최소 4GB, 권장 8GB 이상
- **저장공간**: 최소 2GB 여유 공간
- **권한**: 관리자 권한 (선택사항)

## 🚀 빠른 빌드 (권장)

### 방법 1: 배치 파일 사용 (가장 간단)
```batch
# 1. 이 저장소를 클론 또는 다운로드
# 2. build_windows.exe.bat 더블클릭
# 3. 자동으로 빌드 진행
# 4. dist 폴더에 exe 파일 생성됨
```

### 방법 2: PowerShell 사용 (고급 옵션)
```powershell
# 관리자 권한 PowerShell에서 실행
.\build_windows.ps1

# 옵션들:
.\build_windows.ps1 -Clean        # 이전 빌드 정리
.\build_windows.ps1 -Debug        # 디버그 모드
.\build_windows.ps1 -NoOneFile    # 단일 파일이 아닌 폴더 형태로 빌드
```

## 🔧 수동 빌드

### 1단계: Python 및 가상환경 설정
```batch
# Python 설치 확인
python --version

# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate.bat
```

### 2단계: 의존성 설치
```batch
# pip 업그레이드
python -m pip install --upgrade pip

# 요구사항 설치
pip install -r requirements.txt

# PyInstaller 설치
pip install pyinstaller
```

### 3단계: EXE 파일 빌드
```batch
# 기본 빌드
pyinstaller --onefile --windowed --name excel_image_labeler inference_labeler.py

# 고급 빌드 (권장)
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
    inference_labeler.py
```

## 📁 빌드 결과물

빌드가 성공하면 다음 파일들이 생성됩니다:

```
📦 dist/
├── excel_image_labeler.exe    # 실행 파일
└── ...

📦 build/
├── excel_image_labeler/       # 빌드 중간 파일들
└── ...
```

## 🎯 실행 방법

### 일반 실행
```batch
# exe 파일 더블클릭 또는
dist\excel_image_labeler.exe
```

### 디버그 모드
```batch
# 콘솔 창과 함께 실행 (오류 확인용)
dist\excel_image_labeler.exe
```

## 🐛 문제 해결

### 빌드 실패 시
1. **Python 버전 확인**: `python --version` (3.8 이상 필요)
2. **pip 업그레이드**: `python -m pip install --upgrade pip`
3. **관리자 권한으로 실행**: PowerShell을 관리자 권한으로 실행
4. **안티바이러스 확인**: 일부 안티바이러스가 PyInstaller를 차단할 수 있음

### 실행 실패 시
1. **Microsoft Visual C++ 재배포 가능 패키지 설치**
   - https://aka.ms/vs/17/release/vc_redist.x64.exe
2. **모든 필수 DLL 파일 확인**
3. **관리자 권한으로 실행**

### 일반적인 오류들
- **"Module not found"**: hidden-import 추가 필요
- **"DLL load failed"**: Visual C++ 재배포 가능 패키지 설치
- **"Permission denied"**: 관리자 권한으로 실행

## 📊 빌드 옵션 설명

| 옵션 | 설명 |
|------|------|
| `--onefile` | 모든 파일을 하나의 exe로 압축 |
| `--windowed` | 콘솔 창 없이 GUI만 표시 |
| `--clean` | 이전 빌드 파일 정리 |
| `--hidden-import` | 명시적으로 import할 모듈 지정 |
| `--exclude-module` | 빌드에서 제외할 모듈 |
| `--upx-dir` | UPX 압축 사용 |

## 🚀 고급 빌드 옵션

### Spec 파일 사용
```batch
# spec 파일로 빌드 (더 세밀한 제어 가능)
pyinstaller excel_image_labeler.spec
```

### 크기 최적화
```batch
# 불필요한 모듈 제외로 크기 줄이기
pyinstaller ^
    --exclude-module tkinter ^
    --exclude-module unittest ^
    --exclude-module email ^
    --upx-dir "" ^
    --onefile --windowed ^
    inference_labeler.py
```

## 📞 지원

빌드 중 문제가 발생하면:

1. **오류 메시지 확인**: 전체 오류 로그를 확인
2. **환경 정보 수집**:
   - Python 버전
   - Windows 버전
   - 설치된 패키지 목록 (`pip list`)
3. **깨끗한 환경에서 재시도**: 가상환경 재생성

## 📝 메모

- **빌드 시간**: 5-15분 정도 소요
- **exe 크기**: 약 50-100MB (모든 의존성 포함)
- **호환성**: 빌드한 Windows 버전과 동일하거나 호환되는 버전에서 실행 가능
- **배포**: exe 파일만 배포하면 됨 (Python 설치 불필요)
