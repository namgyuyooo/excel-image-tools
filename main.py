#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from PySide6 import QtWidgets

from setup_dialog import SetupWindow
from inference_labeler import InferenceLabelerWindow


def main():
    app = QtWidgets.QApplication(sys.argv)

    # 설정 창 표시
    setup_window = SetupWindow()
    result = setup_window.exec()

    if result != QtWidgets.QDialog.Accepted:
        # 사용자가 취소한 경우 종료
        setup_window.deleteLater()
        return

    # 설정값 가져오기
    settings = setup_window.get_settings()

    # 설정된 경로 확인
    if not os.path.exists(settings["csv_path"]):
        QtWidgets.QMessageBox.critical(None, "오류", f"CSV 파일을 찾을 수 없음: {settings['csv_path']}")
        setup_window.deleteLater()
        return

    if not os.path.exists(settings["images_base"]):
        QtWidgets.QMessageBox.warning(None, "경고", f"이미지 디렉토리를 찾을 수 없음: {settings['images_base']}")

    if not os.path.exists(settings["json_base"]):
        QtWidgets.QMessageBox.warning(None, "경고", f"JSON 디렉토리를 찾을 수 없음: {settings['json_base']}")

        # 설정 창에서 경로 설정을 QSettings에 저장
    setup_window.save_paths_to_settings()

    # 설정 창 정리
    setup_window.deleteLater()

    # 라벨링 창 표시
    window = InferenceLabelerWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
