# PySide6 Local Labeler

세그멘테이션 추론 CSV/엑셀과 로컬 이미지 폴더를 함께 열어, 이미지를 보면서 빠르게 라벨링하는 초경량 데스크톱 도구입니다. 실시간 JSON 자동저장과 엑셀로의 일괄 반영을 지원합니다.

## 설치

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

pip install -U pandas openpyxl pillow PySide6
```

## 실행

```bash
python pyside_labeler.py
```

## 입력 파일 템플릿 (CSV/Excel)

- 기본 시트(또는 CSV) 컬럼 예시:
  - `img_path`: 이미지 상대/절대 경로 또는 파일명
  - `origin_class`: 원본 클래스(필터에 사용)
  - `error`: 기타 오류/메타정보
  - `pred_seg_results`: 세그 결과 라벨 리스트(예: `SR-이물; 도금-변색`)
  - `seg_score`: 점수 등 수치

추가로, 라벨 작업을 위한 컬럼을 자유롭게 생성할 수 있습니다. 기본 제공 라벨 컬럼은 `review_label` 입니다.

## 이미지 경로 인식 및 매칭 규칙

1) 기본: `images_base` + `normalize_relative_path(img_path)` 조합이 존재하면 사용
2) 실패 시: `basename_without_ext + _viz.png`를 우선 탐색
3) 그래도 없으면: 상위 폴더에서 `basename.*` 와일드카드 재탐색
4) 원본 이미지 `images_base_orig`, 추가 이미지 `images_base_extra` 도 동일한 규칙으로 탐색

CSV가 UTF-8 BOM(`utf-8-sig`)인 경우 자동 인식합니다.

## UI 개요

- 좌측: 이미지 3분할 패널 (INF | ORG | EXT)
  - INF: 추론/시각화 이미지 (기본 베이스)
  - ORG: 원본 이미지 베이스
  - EXT: 선택적 추가 베이스
  - 상단 상태 배너: Labeled/Unlabeled, NG/OK 대비색, 북마크 표시(★)
  - 하단 상태바: INF/ORG/EXT 파일 존재 상태 표시
  - Fit to window: 창 크기에 맞춰 자동 최대화(해제 시 원본 해상도로 스크롤)

- 우측: 작업 패널(스크롤 가능)
  - Active Label Column 선택, 라벨 옵션 버튼(숫자 단축키 1~9), 드롭다운 편집
  - Filter/Sort: `origin_class`, 텍스트 검색, Label state(All/Labeled/Unlabeled), Only bookmarks, pred_seg_results 필터, Sort by/Desc, Clear sort
  - pred_seg_results 필터: 체크박스 다중 선택 + Exclusive(정확일치) / Exclude(제외)
  - 리스트(미니 작업 큐): 현재 필터에서 작업 대상만 표시, 라벨 여부 아이콘(✅/⏳)
  - Bookmark/Memo: 북마크 토글, 메모 편집/저장
  - Summary: 전체 요약(진행률, 분포 Top 10)
  - Log: 로드/저장/액션 로그

## 작업 흐름

1) File > Open Excel/CSV… 로 CSV/엑셀 로드
2) File > Set Images Base… 로 추론/시각화 이미지 상위 폴더 지정
3) Optional: File > Set Original Images Base… 원본 이미지 폴더 지정
4) Optional: File > Set Extra Images Base… 추가 이미지 폴더 지정
5) Tools > Matching Test… 로 샘플 매칭 성공률 확인
6) 라벨 컬럼 구성: Config > Configure Labels… 에서 한 줄에 `컬럼명: 옵션1, 옵션2, ...` 입력
7) 라벨링: 숫자키(1~9) 또는 버튼/드롭다운으로 값 할당 → JSON 자동 저장 → 리스트/통계/요약 즉시 갱신 → 다음 항목 자동 이동(필요시 좌/우 화살표로 이동)
8) Export: File > Apply JSON → Excel… 로 새 엑셀 파일에 일괄 반영(원본 보존)

## 단축키

- 좌/우 화살표: Prev / Next
- 숫자 1~9: Active Label Column 의 i번째 옵션 즉시 적용

## 필터 상세

- origin_class: 드롭다운
- Text contains: `img_path`, `filename`, `pred_seg_results` 에 대한 부분일치
- Label state: All / Labeled / Unlabeled
- Only unlabeled(레거시 체크박스): 호환 유지
- Only bookmarks: 북마크 항목만 표시(JSON 기준)
- pred_seg_results:
  - 체크박스 다중 선택. 항목은 CSV의 `pred_seg_results`에서 자동 추출
  - 분리 규칙: 세미콜론(;) / 콤마(,) / 전각 구분자(；，)
  - Exclusive: 선택 항목만 “정확히” 포함된 경우만 유지(집합이 동일)
  - Exclude: 선택 항목이 포함된 행은 제외
  - 기본: 선택 항목 중 하나라도 포함되면 유지
- Sort by: 임의 컬럼 정렬, Clear sort로 즉시 해제(작업 순서 유지에 유용)

## 저장과 복원

- 자동저장(JSON): 라벨/북마크/메모는 즉시 JSON(`{엑셀명}_labels.json`) 에 기록
- 엑셀 내보내기: 새 파일로 복사 생성 후(JSON → Excel) 값만 일괄 반영
- 세션 복원: 마지막 `excel_path`, `images_base`, `images_base_orig`, `images_base_extra` 는 `QSettings`에 저장되어 재시작 시 자동 복원

## 조작 팁

- 목록에서 현재 항목은 항상 선택 상태로 유지됩니다.
- Unlabeled 필터 상태에서 라벨을 지정하면 해당 항목만 리스트에서 제거되고 다음 항목으로 진행합니다(전체 재정렬/재구성 없음).
- 배너는 NG 시 붉은색, OK/기타 시 녹색으로 표시되어 대비가 큼.
- 하단 상태바에 INF/ORG/EXT의 파일 유무가 상시 표시됩니다.

## 문제 해결

- 매칭이 안 되는 경우: `img_path` 가 실제 파일과 일치하는지, `_viz.png` 변형 규칙이 맞는지 확인하세요. 상이하면 와일드카드 검색이 수행됩니다.
- CSV 인코딩: UTF-8 BOM(`utf-8-sig`) 문제로 컬럼이 비는 경우가 있어 자동 감지합니다.
- 성능: 이미지 폴더가 네트워크 드라이브면 느려질 수 있습니다. 로컬 디스크 권장. 필요 시 창 크기에 맞춤(Scaling) 사용.
- 경고: 일부 환경에서 `DeprecationWarning: datetime.utcnow()`가 출력될 수 있으나 기능에 영향은 없습니다.
- 엑셀 저장 실패: 대상 엑셀이 열려있지 않은지 확인하세요.

## 레포 구성 요약

- `pyside_labeler.py`: 메인 데스크톱 라벨러
- `create_excel_from_seg_csv.py`: 세그 CSV → 이미지 포함 엑셀 생성 스크립트
- `test_match.py`: 이미지 경로 매칭 진단

## 라이선스

MIT License