#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import hashlib
import re
from datetime import datetime
try:
    # Python 3.11+
    from datetime import UTC as _UTC
except Exception:
    from datetime import timezone as _tz
    _UTC = _tz.utc
from typing import Dict, List, Optional, Tuple
import gc
import psutil

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

# Import from separated modules
from utils import (
    get_memory_usage, check_memory_limit, force_garbage_collection, get_system_memory,
    parse_pred_list, extract_detail_from_json, ensure_object_dtype, default_json_path,
    load_label_store, save_label_store, apply_json_to_excel, get_json_entry,
    upsert_json_entry, merge_json_into_df, is_xlsx, thumb_cache_path, build_thumb_if_needed,
    resolve_image_path, CSV_CONFIGS
)
from setup_dialog import SetupWindow

# Reuse path resolution from the existing module
from create_excel_from_seg_csv import resolve_image_path


class InferenceLabelerWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: dict = None) -> None:
        super().__init__()
        print("🚀 InferenceLabelerWindow 초기화 시작")

        # 창 기본 설정
        self.setWindowTitle("추론 결과 라벨링 도구")
        self.resize(1400, 900)

        # 설정에서 경로 가져오기
        if settings:
            self.csv_path = settings.get("csv_path", CSV_CONFIGS["inference"]["csv_path"])
            self.images_base = settings.get("images_base", CSV_CONFIGS["inference"]["images_base"])
            self.json_base = settings.get("json_base", CSV_CONFIGS["inference"]["json_base"])
            csv_type = settings.get("csv_type", "inference")
            self.setWindowTitle(f"추론 결과 라벨링 도구 - {csv_type.upper()} ({os.path.basename(self.csv_path)})")
        else:
            # 기본값 사용
            self.csv_path = CSV_CONFIGS["inference"]["csv_path"]
            self.images_base = CSV_CONFIGS["inference"]["images_base"]
            self.json_base = CSV_CONFIGS["inference"]["json_base"]

        # State 초기화
        self.df: Optional[pd.DataFrame] = None
        self.json_path: str = ""
        self.col_indices: Dict[str, int] = {}
        self.current_idx: int = 0
        self.filtered_indices: List[int] = []
        self.active_label_col: str = "action"

        # UI 구축
        self._build_ui()

        # 데이터 로딩
        self._auto_load_data()

        print("✅ InferenceLabelerWindow 초기화 완료")

    def _build_ui(self) -> None:
        """간단하고 안정적인 UI 구축"""
        print("🔧 UI 구축 시작")

        # 중앙 위젯 생성
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # 메인 레이아웃
        main_layout = QtWidgets.QHBoxLayout(central_widget)

        # 1. 왼쪽 패널: 이미지
        self._create_image_panel(main_layout)

        # 2. 가운데 패널: 컨트롤
        self._create_controls_panel(main_layout)

        # 3. 오른쪽 패널: 테이블
        self._create_table_panel(main_layout)

        print("✅ UI 구축 완료")

    def _create_image_panel(self, parent_layout):
        """이미지 패널 생성"""
        print("🖼️ 이미지 패널 생성")

        # 이미지 패널
        image_panel = QtWidgets.QWidget()
        image_layout = QtWidgets.QVBoxLayout(image_panel)

        # 스크롤 영역
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setMinimumWidth(400)

        # 이미지 라벨
        self.image_label = QtWidgets.QLabel("이미지가 로드되지 않음")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet("border: 2px dashed #ccc;")

        self.scroll_area.setWidget(self.image_label)

        # 상태 표시
        self.image_status_bar = QtWidgets.QLabel("이미지 상태: 준비")
        self.path_label = QtWidgets.QLabel("경로: 없음")

        # 레이아웃에 추가
        image_layout.addWidget(self.image_status_bar)
        image_layout.addWidget(self.scroll_area)
        image_layout.addWidget(self.path_label)

        parent_layout.addWidget(image_panel, 1)

    def _create_controls_panel(self, parent_layout):
        """컨트롤 패널 생성"""
        print("🎛️ 컨트롤 패널 생성")

        # 컨트롤 패널
        controls_panel = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls_panel)

        # 타이틀
        title = QtWidgets.QLabel("라벨링 컨트롤")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        controls_layout.addWidget(title)

        # 현재 정보
        self.lbl_current_info = QtWidgets.QLabel("데이터가 로드되지 않음")
        self.lbl_current_info.setWordWrap(True)
        self.lbl_current_info.setStyleSheet("border: 1px solid #ddd; padding: 5px;")
        controls_layout.addWidget(self.lbl_current_info)

        # 북마크
        bookmark_group = QtWidgets.QGroupBox("북마크")
        bookmark_layout = QtWidgets.QVBoxLayout(bookmark_group)

        self.btn_toggle_bookmark = QtWidgets.QPushButton("북마크 토글")
        self.lbl_bookmark_status = QtWidgets.QLabel("북마크: ❌")

        bookmark_layout.addWidget(self.btn_toggle_bookmark)
        bookmark_layout.addWidget(self.lbl_bookmark_status)

        controls_layout.addWidget(bookmark_group)

        # 라벨링 버튼들
        labeling_group = QtWidgets.QGroupBox("라벨링")
        labeling_layout = QtWidgets.QVBoxLayout(labeling_group)

        # 라벨 버튼들 생성
        self._create_label_buttons(labeling_layout)

        controls_layout.addWidget(labeling_group)

        # 빈 공간
        controls_layout.addStretch()

        parent_layout.addWidget(controls_panel, 0)

    def _create_table_panel(self, parent_layout):
        """테이블 패널 생성"""
        print("📊 테이블 패널 생성")

        # 테이블 패널
        table_panel = QtWidgets.QWidget()
        table_layout = QtWidgets.QVBoxLayout(table_panel)

        # 타이틀
        table_title = QtWidgets.QLabel("데이터 미리보기")
        table_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        table_layout.addWidget(table_title)

        # 테이블 생성
        self.table = QtWidgets.QTableWidget()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(400)

        table_layout.addWidget(self.table)

        parent_layout.addWidget(table_panel, 1)

    def _create_label_buttons(self, layout):
        """라벨링 버튼들 생성"""
        labels = ["OK", "애매한 OK", "NG", "애매한 NG", "보류", "SRLogicOK"]

        for label in labels:
            button = QtWidgets.QPushButton(label)
            button.setMinimumHeight(30)
            button.clicked.connect(lambda checked, text=label: self._assign_label_by_button(text))
            layout.addWidget(button)

    def _assign_label_by_button(self, label_text):
        """버튼으로 라벨 할당"""
        print(f"라벨 할당: {label_text}")

    def _auto_load_data(self):
        """데이터 자동 로딩"""
        print("📊 데이터 로딩 시작")
        if os.path.exists(self.csv_path):
            self.load_csv_data()
        else:
            print(f"CSV 파일을 찾을 수 없음: {self.csv_path}")

    def load_csv_data(self) -> None:
        """CSV 데이터 로딩"""
        try:
            print(f"CSV 파일 로딩: {self.csv_path}")
            self.df = pd.read_csv(self.csv_path)
            print(f"데이터 로드 완료: {len(self.df)} 행")

            # 필터링 인덱스 초기화
            self.filtered_indices = list(range(len(self.df)))

            # 테이블 업데이트
            self.refresh_table()

        except Exception as e:
            print(f"데이터 로딩 오류: {e}")

    def refresh_table(self) -> None:
        """테이블 새로고침"""
        if self.df is None:
            return

        if not hasattr(self, 'table') or self.table is None:
            print("테이블 위젯이 존재하지 않음")
            return

        try:
            # 테이블 설정
            display_cols = ["File_path", "Result", "action"]
            available_cols = [col for col in display_cols if col in self.df.columns]

            self.table.setRowCount(min(100, len(self.df)))  # 최대 100행만 표시
            self.table.setColumnCount(len(available_cols))
            self.table.setHorizontalHeaderLabels(available_cols)

            # 데이터 채우기
            for i in range(min(100, len(self.df))):
                for j, col in enumerate(available_cols):
                    value = str(self.df.iloc[i][col])
                    if len(value) > 50:
                        value = value[:47] + "..."
                    self.table.setItem(i, j, QtWidgets.QTableWidgetItem(value))

            print(f"테이블 업데이트 완료: {min(100, len(self.df))} 행")

        except Exception as e:
            print(f"테이블 업데이트 오류: {e}")


def main():
    app = QtWidgets.QApplication(sys.argv)

    # 설정 창
    setup_window = SetupWindow()
    result = setup_window.exec()

    if result != QtWidgets.QDialog.Accepted:
        return

    # 메인 창
    settings = setup_window.get_settings()
    window = InferenceLabelerWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

