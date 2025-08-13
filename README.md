# Image Analysis Excel Generator

Excel 파일에 이미지와 분석 결과를 통합하여 시각적 데이터 분석을 지원하는 Python 도구입니다.

## 기능

- 📷 **이미지 쌍 매칭**: BMP 원본 이미지와 PNG 시각화 이미지를 자동으로 매칭
- 📊 **추론 결과 통합**: 여러 `inference_results.csv` 파일의 결과를 통합
- 📈 **DMT 분석 결과 포함**: 상세 분석 결과 CSV 파일과 병합
- 🗂️ **Excel 필터링**: 자동 필터 기능이 활성화된 Excel 파일 생성
- 🖼️ **이미지 삽입**: 적절한 비율로 리사이즈된 이미지를 Excel 셀에 삽입
- 🔍 **다국어 지원**: 한글 자소 분리 문제 해결

## 파일 구조

```
v0.3/
├── SR/                             # SR 관련 이미지 및 결과
│   ├── images/
│   │   ├── good/
│   │   └── bad/
│   └── inference_results.csv
├── OSP_패턴/                       # OSP 패턴 관련 데이터
├── 도금/                           # 도금 관련 데이터
├── 패턴/                           # 패턴 관련 데이터
├── OSP_도금/                       # OSP 도금 관련 데이터
├── 본드핑거/                       # 본드핑거 관련 데이터
├── DMT_poc 상세결과 - 시트14 (1).csv  # DMT 분석 결과
└── Python 스크립트들
```

## 설치 및 실행

### 1. 가상환경 설정

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 2. 의존성 설치

```bash
pip install openpyxl pillow
```

### 3. 스크립트 실행

#### 통합 실행 파일 사용 (권장)
```bash
python run_analysis.py
```

#### 개별 스크립트 실행

##### 기본 이미지-결과 매칭 Excel 생성
```bash
python create_excel_with_results.py
```

##### 필터링 최적화 Excel 생성
```bash
python create_excel_cell_images.py
```

##### DMT 결과까지 포함한 통합 Excel 생성
```bash
python create_excel_merged.py
```

## 통합 실행 파일

### `run_analysis.py` - 메인 실행 파일 🚀

대화형 메뉴를 통해 모든 기능에 접근할 수 있는 통합 실행 파일입니다.

**기능:**
- 📋 직관적인 메뉴 인터페이스
- 🔍 의존성 자동 확인
- 📦 패키지 자동 설치
- 🐍 가상환경 설정 지원
- ⚠️ 안전한 실행 (확인 메시지)

**사용법:**
```bash
python run_analysis.py
```

## 출력 파일

### `image_analysis_results.xlsx`
- 기본 이미지 쌍과 추론 결과가 포함된 Excel 파일
- 전체 데이터 처리

### `image_pairs_with_filter.xlsx`
- 필터링에 최적화된 Excel 파일
- 셀 기반 이미지 배치
- 전체 데이터 처리

### `merged_analysis_results.xlsx`
- DMT 분석 결과까지 포함한 완전한 통합 Excel 파일
- 전체 7,917개 파일 처리
- 이미지 없는 DMT 데이터도 포함

## Excel 파일 컬럼 구성

| 컬럼명 | 설명 | 비고 |
|--------|------|------|
| `filename` | 파일명 | 기본 키 |
| `img` | 원본 BMP 이미지 | 1:1 비율 (150×150px) |
| `viz_img` | 시각화 PNG 이미지 | 2:1 비율 (200×100px) |
| `gt_status` | Ground Truth 상태 | OK/NG |
| `pred_status` | 예측 결과 | OK/NG |
| `dominant_class` | 주요 분류 결과 | 클래스명 |
| `csv_source` | 추론 결과 소스 폴더 | 폴더명 |
| `dmt_category` | DMT 구분 | overkill/underkill 등 |
| `gt_status_real` | DMT GT 실제 상태 | OK/NG |

## 특징

### 🖼️ 이미지 처리
- **BMP 이미지**: 1:1 비율 유지하여 150×150 픽셀로 리사이즈
- **PNG 이미지**: 2:1 비율 유지하여 200×100 픽셀로 리사이즈
- 자동 RGB 변환 및 고품질 리샘플링

### 📊 데이터 통합
- 여러 폴더의 `inference_results.csv` 파일 자동 검색 및 통합
- DMT 상세 분석 결과와 파일명 기준 매칭
- 이미지가 없는 데이터도 텍스트로 포함

### 🔍 필터링 및 정렬
- Excel 자동 필터 기능 활성화
- 모든 컬럼에 대한 필터링 및 정렬 지원
- 한글 자소 분리 문제 해결 (Unicode NFC 정규화)

## 신규 기능 (2025-08)

- 세그멘테이션 CSV 기반 Excel 생성: `create_excel_from_seg_csv.py`
  - `inference_results.csv`(헤더: `img_path, origin_class, error, pred_seg_results, seg_score`)를 읽어 원본 이미지(또는 `*_viz.png`)를 마지막 컬럼에 삽입한 `.xlsx` 생성
  - CSV가 UTF-8 BOM(`utf-8-sig`)인 경우도 자동 인식
  - `img_path`를 기준으로 이미지 매칭. 없으면 파일명/확장자 와일드카드 검색, `<base>_viz.png` 우선
  - 임베디드 썸네일 기본 크기 180×180(px), 행 높이 180(point)

- 라벨링 GUI: `streamlit_review.py`
  - 1) 엑셀/CSV 파일 선택(업로드/경로 입력), 2) 이미지 상위 폴더 선택, 3) 매칭 테스트(성공률 표시), 4) 검증/라벨링 시작
  - 이미지 중심 탭: 큰 미리보기, Prev/Next, 필터(클래스/텍스트/미라벨), 빠른 라벨 버튼, 단일 셀 즉시 저장(엑셀 내 임베디드 이미지는 보존)
  - 표 탭: 그리드 정렬/필터, 드롭다운 편집, 자동/수동 저장
  - 여러 라벨 컬럼을 한 번에 정의 가능: 각 줄에 `컬럼명: 옵션1, 옵션2, ...`

## 설치 (권장)

```bash
python3 -m venv venv
source venv/bin/activate
pip install openpyxl pillow pandas streamlit streamlit-aggrid
# (옵션) 파일 감시 성능 향상
pip install watchdog
```

## 실행 방법

- 세그 CSV → 엑셀 생성
```bash
python create_excel_from_seg_csv.py
```
  - 기본 경로는 스크립트 내 상단의 `IMAGES_BASE`, `CSV_PATH`, `output_file`를 수정

- 라벨링 GUI
```bash
streamlit run streamlit_review.py
```
  - 브라우저에서 `http://localhost:8501` 접속
  - 상단 단계 순서대로 진행: 파일 선택 → 이미지 상위 폴더 선택 → 매칭 테스트 → 라벨링

## 사용 팁

- 엑셀 파일이 열려 있으면 저장이 실패할 수 있습니다. 편집 중에는 엑셀을 닫아주세요.
- 대량 데이터에서 미리보기 성능이 느리면 이미지 크기를 줄이거나 `watchdog` 설치를 권장합니다.
- 썸네일 크기/열 너비/행 높이 등은 스크립트에서 조절 가능합니다.

## 로그 기능

스크립트 실행 시 상세한 로그가 출력됩니다:

```
=== 추론 결과 파일 검색 시작 ===
발견된 CSV 파일 수: 6
[1/6] CSV 파일 로딩 중: /path/to/inference_results.csv
   └── 45개 결과 로딩 완료

=== 이미지 파일 검색 시작 ===
PNG 파일 (viz) 검색 중...
발견된 PNG 파일 수: 893

=== 엑셀 파일에 이미지 및 결과 삽입 시작 ===
[1/100] 처리 중: filename
   └── BMP 이미지 삽입 완료 (400x400 → 150x150)
   └── PNG 이미지 삽입 완료 (800x400 → 200x100)
```

## 주의사항

- 대용량 데이터 처리 시 메모리 사용량 고려
- 이미지 파일 경로와 CSV 파일 경로가 올바른지 확인
- Excel 파일은 `.gitignore`에 포함되어 버전 관리에서 제외됨

## 라이선스

MIT License

## 기여

이슈나 개선사항이 있으시면 언제든지 제보해 주세요!