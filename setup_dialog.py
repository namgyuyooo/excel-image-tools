#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

from utils import CSV_CONFIGS, detect_csv_type, resolve_image_path


class SetupWindow(QtWidgets.QDialog):
    """설정 페이지 - CSV 파일과 이미지 폴더 경로를 설정하고 매칭 테스트를 수행합니다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CSV 라벨링 도구 설정")
        self.resize(900, 700)
        self.setModal(True)

        # 설정값
        self.csv_path = ""
        self.images_base = ""
        self.json_base = ""
        self.csv_type = "report"  # 리포트 단일로 고정

        self._build_ui()
        self._load_default_paths()

    def _build_ui(self):
        """UI 구성"""
        main_layout = QtWidgets.QVBoxLayout(self)

        # 제목
        title_label = QtWidgets.QLabel("CSV 라벨링 도구 설정")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1976d2; margin: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 스크롤 영역 생성
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # 스크롤될 컨텐츠 위젯
        content_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content_widget)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # CSV 파일 선택
        csv_group = QtWidgets.QGroupBox("CSV 파일 선택")
        csv_layout = QtWidgets.QVBoxLayout(csv_group)

        csv_info = QtWidgets.QLabel("라벨링할 CSV 파일을 선택하세요.")
        csv_layout.addWidget(csv_info)

        csv_path_layout = QtWidgets.QHBoxLayout()
        self.csv_path_edit = QtWidgets.QLineEdit()
        self.csv_path_edit.setPlaceholderText("CSV 파일 경로를 입력하거나 선택하세요")
        self.csv_path_edit.setReadOnly(True)
        csv_path_layout.addWidget(self.csv_path_edit)

        self.csv_browse_btn = QtWidgets.QPushButton("파일 찾기")
        self.csv_browse_btn.clicked.connect(self._browse_csv)
        csv_path_layout.addWidget(self.csv_browse_btn)

        csv_layout.addLayout(csv_path_layout)
        layout.addWidget(csv_group)

        # 이미지 폴더 선택
        images_group = QtWidgets.QGroupBox("이미지 폴더 선택")
        images_layout = QtWidgets.QVBoxLayout(images_group)

        images_info = QtWidgets.QLabel("CSV 파일의 이미지들이 저장된 폴더를 선택하세요.")
        images_layout.addWidget(images_info)

        images_path_layout = QtWidgets.QHBoxLayout()
        self.images_path_edit = QtWidgets.QLineEdit()
        self.images_path_edit.setPlaceholderText("이미지 폴더 경로를 입력하거나 선택하세요")
        self.images_path_edit.setReadOnly(True)
        images_path_layout.addWidget(self.images_path_edit)

        self.images_browse_btn = QtWidgets.QPushButton("폴더 찾기")
        self.images_browse_btn.clicked.connect(self._browse_images)
        images_path_layout.addWidget(self.images_browse_btn)

        images_layout.addLayout(images_path_layout)
        layout.addWidget(images_group)

        # JSON 폴더 선택
        json_group = QtWidgets.QGroupBox("JSON 폴더 선택")
        json_layout = QtWidgets.QVBoxLayout(json_group)

        json_info = QtWidgets.QLabel("JSON 파일들이 저장된 폴더를 선택하세요.")
        json_layout.addWidget(json_info)

        json_path_layout = QtWidgets.QHBoxLayout()
        self.json_path_edit = QtWidgets.QLineEdit()
        self.json_path_edit.setPlaceholderText("JSON 폴더 경로를 입력하거나 선택하세요")
        self.json_path_edit.setReadOnly(True)
        json_path_layout.addWidget(self.json_path_edit)

        self.json_browse_btn = QtWidgets.QPushButton("폴더 찾기")
        self.json_browse_btn.clicked.connect(self._browse_json)
        json_path_layout.addWidget(self.json_browse_btn)

        json_layout.addLayout(json_path_layout)
        layout.addWidget(json_group)

        # CSV 타입 선택 (리포트 단일로 고정)
        type_group = QtWidgets.QGroupBox("CSV 타입 설정")
        type_layout = QtWidgets.QVBoxLayout(type_group)

        type_info = QtWidgets.QLabel("CSV 타입: 리포트 단일 (Report Single)")
        type_info.setStyleSheet("font-weight: bold; color: #1976d2;")
        type_layout.addWidget(type_info)

        # 고정된 타입 표시
        type_display = QtWidgets.QLabel("📊 리포트 CSV 파일을 사용합니다.")
        type_display.setStyleSheet("color: #666; font-style: italic;")
        type_layout.addWidget(type_display)

        layout.addWidget(type_group)

        # 마지막 경로 설정 복원 버튼
        restore_group = QtWidgets.QGroupBox("저장된 경로 복원")
        restore_layout = QtWidgets.QVBoxLayout(restore_group)

        restore_info = QtWidgets.QLabel("이전에 사용한 경로 설정을 복원할 수 있습니다.")
        restore_layout.addWidget(restore_info)

        restore_buttons_layout = QtWidgets.QHBoxLayout()

        self.btn_restore_paths = QtWidgets.QPushButton("저장된 경로 복원")
        self.btn_restore_paths.clicked.connect(self._restore_saved_paths)
        restore_buttons_layout.addWidget(self.btn_restore_paths)

        restore_layout.addLayout(restore_buttons_layout)
        layout.addWidget(restore_group)

        # 매칭 테스트 결과
        test_group = QtWidgets.QGroupBox("매칭 테스트 결과")
        test_layout = QtWidgets.QVBoxLayout(test_group)

        self.test_result_label = QtWidgets.QLabel("CSV 파일과 이미지 폴더를 선택한 후 테스트를 실행하세요.")
        self.test_result_label.setWordWrap(True)
        test_layout.addWidget(self.test_result_label)

        test_buttons_layout = QtWidgets.QHBoxLayout()
        self.test_btn = QtWidgets.QPushButton("매칭 테스트 실행")
        self.test_btn.clicked.connect(self._run_matching_test)
        self.test_btn.setEnabled(False)
        test_buttons_layout.addWidget(self.test_btn)
        test_layout.addLayout(test_buttons_layout)

        layout.addWidget(test_group)

        # 스트레치 추가로 스크롤 영역을 채움
        layout.addStretch()

        # 진행 버튼 (스크롤 영역 바깥에 위치)
        button_layout = QtWidgets.QHBoxLayout()

        self.cancel_btn = QtWidgets.QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.start_btn = QtWidgets.QPushButton("라벨링 시작")
        self.start_btn.clicked.connect(self.accept)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)

        main_layout.addLayout(button_layout)

    def _load_default_paths(self):
        """기본 경로 로드"""
        # 리포트 단일 타입이 기본값
        self.csv_type = "report"
        self.csv_path = CSV_CONFIGS["report"]["csv_path"]
        self.images_base = CSV_CONFIGS["report"]["images_base"]
        self.json_base = CSV_CONFIGS["report"]["json_base"]

        self.csv_path_edit.setText(self.csv_path)
        self.images_path_edit.setText(self.images_base)
        self.json_path_edit.setText(self.json_base)

        self._update_test_button_state()

        # 저장된 경로가 있으면 복원 시도
        self._try_restore_saved_paths()

    def _restore_saved_paths(self):
        """저장된 경로 설정을 복원"""
        self.load_paths_from_settings()
        self.csv_path_edit.setText(self.csv_path)
        self.images_path_edit.setText(self.images_base)
        self.json_path_edit.setText(self.json_base)

        self._update_test_button_state()
        print("저장된 경로 설정이 복원되었습니다.")

    def _try_restore_saved_paths(self):
        """초기화 시 저장된 경로가 있으면 자동으로 복원 시도"""
        settings = QtCore.QSettings("rtm", "inference_labeler")
        last_csv_path = settings.value("last_csv_path", "")
        last_images_base = settings.value("last_images_base", "")
        last_json_base = settings.value("last_json_base", "")

        if last_csv_path and os.path.exists(last_csv_path):
            self.csv_path = last_csv_path
            self.csv_path_edit.setText(self.csv_path)

        if last_images_base and os.path.exists(last_images_base):
            self.images_base = last_images_base
            self.images_path_edit.setText(self.images_base)

        if last_json_base and os.path.exists(last_json_base):
            self.json_base = last_json_base
            self.json_path_edit.setText(self.json_base)

        if self.csv_path != CSV_CONFIGS[self.csv_type]["csv_path"] or \
           self.images_base != CSV_CONFIGS[self.csv_type]["images_base"] or \
           self.json_base != CSV_CONFIGS[self.csv_type]["json_base"]:
            print("저장된 경로 설정이 복원되었습니다.")



    def _browse_csv(self):
        """CSV 파일 찾기"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "CSV 파일 선택",
            os.path.expanduser("~/Downloads"),
            "CSV 파일 (*.csv);;모든 파일 (*)"
        )

        if file_path:
            self.csv_path = file_path
            self.csv_path_edit.setText(file_path)

            # 리포트 단일 타입으로 고정되어 있으므로 별도 처리 불필요
            self._update_test_button_state()

    def _browse_images(self):
        """이미지 폴더 찾기"""
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "이미지 폴더 선택",
            os.path.expanduser("~/Downloads")
        )

        if folder_path:
            self.images_base = folder_path
            self.images_path_edit.setText(folder_path)
            self._update_test_button_state()

    def _browse_json(self):
        """JSON 폴더 찾기"""
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "JSON 폴더 선택",
            os.path.expanduser("~/Downloads")
        )

        if folder_path:
            self.json_base = folder_path
            self.json_path_edit.setText(folder_path)
            self._update_test_button_state()

    def _update_test_button_state(self):
        """테스트 버튼 활성화 상태 업데이트"""
        can_test = bool(self.csv_path and self.images_base and self.json_base and
                       os.path.exists(self.csv_path) and os.path.exists(self.images_base) and os.path.exists(self.json_base))
        self.test_btn.setEnabled(can_test)

    def _run_matching_test(self):
        """매칭 테스트 실행"""
        if not self.csv_path or not self.images_base:
            return

        try:
            # CSV 파일 로드
            df = pd.read_csv(self.csv_path, nrows=100)  # 처음 100행만 테스트

            if "File_path" not in df.columns:
                self.test_result_label.setText("❌ CSV 파일에 'File_path' 컬럼이 없습니다.")
                return

            # 이미지 매칭 테스트
            total_rows = len(df)
            matched_count = 0
            sample_matches = []

            for idx, row in df.iterrows():
                file_path = row["File_path"]
                if pd.isna(file_path) or not str(file_path).strip():
                    continue

                resolved_path = resolve_image_path(self.images_base, str(file_path))
                if os.path.exists(resolved_path):
                    matched_count += 1
                    if len(sample_matches) < 3:
                        sample_matches.append(os.path.basename(resolved_path))

            # 결과 표시
            match_rate = (matched_count / total_rows * 100) if total_rows > 0 else 0

            if match_rate > 80:
                status = "✅"
                color = "green"
                self.start_btn.setEnabled(True)
            elif match_rate > 50:
                status = "⚠️"
                color = "orange"
                self.start_btn.setEnabled(True)
            else:
                status = "❌"
                color = "red"
                self.start_btn.setEnabled(False)

            result_text = f"{status} 매칭 테스트 결과:\n"
            result_text += f"전체 행: {total_rows:,}개\n"
            result_text += f"매칭 성공: {matched_count:,}개\n"
            result_text += f"매칭률: {match_rate:.1f}%\n\n"

            if sample_matches:
                result_text += f"샘플 매칭 파일:\n"
                for match in sample_matches:
                    result_text += f"  • {match}\n"

            self.test_result_label.setText(result_text)
            self.test_result_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        except Exception as e:
            self.test_result_label.setText(f"❌ 테스트 실행 중 오류 발생:\n{str(e)}")
            self.test_result_label.setStyleSheet("color: red; font-weight: bold;")

    def get_settings(self):
        """설정값 반환"""
        return {
            "csv_path": self.csv_path,
            "images_base": self.images_base,
            "json_base": self.json_base,
            "csv_type": self.csv_type
        }

    def save_paths_to_settings(self):
        """경로 설정을 QSettings에 저장"""
        settings = QtCore.QSettings("rtm", "inference_labeler")
        settings.setValue("last_csv_path", self.csv_path)
        settings.setValue("last_images_base", self.images_base)
        settings.setValue("last_json_base", self.json_base)
        settings.setValue("last_csv_type", self.csv_type)
        print(f"경로 설정 저장됨: CSV={self.csv_path}, 이미지={self.images_base}, JSON={self.json_base}")

    def load_paths_from_settings(self):
        """QSettings에서 마지막 경로 설정을 로드"""
        settings = QtCore.QSettings("rtm", "inference_labeler")
        last_csv_path = settings.value("last_csv_path", "")
        last_images_base = settings.value("last_images_base", "")
        last_json_base = settings.value("last_json_base", "")
        last_csv_type = settings.value("last_csv_type", "report")

        if last_csv_path and os.path.exists(last_csv_path):
            self.csv_path = last_csv_path
        if last_images_base and os.path.exists(last_images_base):
            self.images_base = last_images_base
        if last_json_base and os.path.exists(last_json_base):
            self.json_base = last_json_base
        if last_csv_type in ["inference", "report"]:
            self.csv_type = last_csv_type

        print(f"저장된 경로 설정 로드됨: CSV={self.csv_path}, 이미지={self.images_base}, JSON={self.json_base}")

    def accept(self):
        """라벨링 시작 버튼 클릭 시 설정값 검증"""
        # 설정값 검증
        if not self.csv_path or not os.path.exists(self.csv_path):
            QtWidgets.QMessageBox.critical(self, "오류", "CSV 파일을 찾을 수 없거나 선택되지 않았습니다.")
            return

        if not self.images_base or not os.path.exists(self.images_base):
            QtWidgets.QMessageBox.critical(self, "오류", "이미지 폴더를 찾을 수 없거나 선택되지 않았습니다.")
            return

        if not self.json_base or not os.path.exists(self.json_base):
            QtWidgets.QMessageBox.critical(self, "오류", "JSON 폴더를 찾을 수 없거나 선택되지 않았습니다.")
            return

        # 모든 검증 통과 시 부모의 accept() 호출
        super().accept()
