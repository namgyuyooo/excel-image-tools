#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

from openpyxl import load_workbook

# Reuse path resolution from the existing module
from create_excel_from_seg_csv import resolve_image_path, normalize_relative_path
import glob


def ensure_object_dtype(df: pd.DataFrame, column: str) -> None:
    try:
        df[column] = df[column].astype("object")
    except Exception:
        pass


def default_json_path(xlsx_path: str) -> str:
    base = os.path.basename(xlsx_path)
    root, _ = os.path.splitext(base)
    parent = os.path.dirname(xlsx_path) or os.getcwd()
    return os.path.join(parent, f"{root}_labels.json")


def load_label_store(json_path: str) -> dict:
    if not json_path or not os.path.exists(json_path):
        return {"version": 1, "updated_at": None, "labels": {}}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "labels" in data:
                return data
    except Exception:
        pass
    return {"version": 1, "updated_at": None, "labels": {}}


def save_label_store(json_path: str, store: dict) -> None:
    store["updated_at"] = datetime.utcnow().isoformat()
    tmp = json_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, json_path)


def apply_json_to_excel(json_path: str, xlsx_path: str, sheet_name: str, col_indices: Dict[str, int], df: pd.DataFrame) -> int:
    store = load_label_store(json_path)
    labels = store.get("labels", {})
    applied = 0
    wb = load_workbook(xlsx_path)
    ws = wb[sheet_name]
    for key, entry in labels.items():
        try:
            row_idx = int(key)
        except Exception:
            continue
        excel_row = row_idx + 2
        values = entry.get("values", {})
        for col_name, val in values.items():
            idx = col_indices.get(col_name)
            if idx is None:
                continue
            try:
                ws.cell(row=excel_row, column=idx, value=val)
                applied += 1
                if col_name in df.columns:
                    df.at[row_idx, col_name] = val
            except Exception:
                pass
    wb.save(xlsx_path)
    wb.close()
    return applied


def get_json_entry(json_path: str, row_idx: int) -> dict:
    store = load_label_store(json_path)
    key = str(row_idx)
    return store.get("labels", {}).get(key) or {}


def upsert_json_entry(json_path: str, row_idx: int, updater: Dict[str, object]) -> None:
    store = load_label_store(json_path)
    key = str(row_idx)
    entry = store["labels"].get(key) or {}
    for k, v in updater.items():
        entry[k] = v
    store["labels"][key] = entry
    save_label_store(json_path, store)


def merge_json_into_df(json_path: str, df: pd.DataFrame, label_columns: List[str]) -> None:
    """Load existing JSON labels and reflect into DataFrame so work can resume after restart."""
    store = load_label_store(json_path)
    labels = store.get("labels", {})
    for key, entry in labels.items():
        try:
            ridx = int(key)
        except Exception:
            continue
        if ridx not in df.index:
            continue
        values = entry.get("values", {})
        for col, val in values.items():
            if col in label_columns:
                try:
                    df.at[ridx, col] = val
                except Exception:
                    pass

def is_xlsx(path: str) -> bool:
    try:
        return os.path.isfile(path) and path.lower().endswith(".xlsx")
    except Exception:
        return False


def thumb_cache_path(images_base: str, resolved_path: str, target_edge: int) -> str:
    rel = os.path.relpath(resolved_path, images_base)
    key = hashlib.md5(f"{rel}|{target_edge}".encode("utf-8")).hexdigest()
    cache_dir = os.path.join(images_base, ".thumb_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{key}.png")


def build_thumb_if_needed(images_base: str, resolved_path: str, target_edge: int) -> str:
    thumb = thumb_cache_path(images_base, resolved_path, target_edge)
    try:
        src_mtime = os.path.getmtime(resolved_path)
        if os.path.exists(thumb) and os.path.getmtime(thumb) >= src_mtime:
            return thumb
        # Use Qt to scale and save
        img = QtGui.QImage(resolved_path)
        if img.isNull():
            return resolved_path
        w, h = img.width(), img.height()
        scale = target_edge / float(max(w, h))
        if scale < 1.0:
            img = img.scaled(int(w * scale), int(h * scale), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        img.save(thumb, "PNG")
        return thumb
    except Exception:
        return resolved_path


class LabelerWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PySide6 Local Labeler")
        self.resize(1400, 900)

        # State
        self.images_base: str = ""  # inference/viz base
        self.images_base_orig: str = ""  # original images base with same sub-structure
        self.excel_path: str = ""
        self.output_excel_path: str = ""
        self.json_path: str = ""
        self.df: Optional[pd.DataFrame] = None
        self.sheet_name: str = "inference_results"
        self.col_indices: Dict[str, int] = {}
        self.label_map: Dict[str, List[str]] = {"review_label": ["OK", "NG", "보류"]}
        self.active_label_col: str = "review_label"
        self.current_idx: int = 0
        self.filtered_indices: List[int] = []
        self.fit_to_window: bool = True
        # Persist settings
        self.settings = QtCore.QSettings("rtm", "pyside_labeler")

        # UI
        self._build_ui()
        self._connect_shortcuts()
        # Try restore last session
        try:
            self.restore_last_session()
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.status = self.statusBar()

        # Menus
        file_menu = self.menuBar().addMenu("File")
        act_open = file_menu.addAction("Open Excel/CSV…")
        act_set_images = file_menu.addAction("Set Images Base…")
        act_export = file_menu.addAction("Apply JSON → Excel…")
        act_set_images_orig = file_menu.addAction("Set Original Images Base…")
        act_quit = file_menu.addAction("Quit")
        act_quit.triggered.connect(self.close)
        act_open.triggered.connect(self.on_open_excel)
        act_set_images.triggered.connect(self.on_set_images_base)
        act_export.triggered.connect(self.on_apply_json)
        act_set_images_orig.triggered.connect(self.on_set_images_base_orig)

        config_menu = self.menuBar().addMenu("Config")
        act_labels = config_menu.addAction("Configure Labels…")
        act_labels.triggered.connect(self.on_configure_labels)

        tools_menu = self.menuBar().addMenu("Tools")
        act_test = tools_menu.addAction("Matching Test…")
        act_test.triggered.connect(self.on_matching_test)

        # Central splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Left: two image previews (inference/viz | original) side-by-side
        images_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        # Inference/Viz panel
        self.scroll_infer = QtWidgets.QScrollArea()
        self.scroll_infer.setWidgetResizable(True)
        self.image_label_infer = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.image_label_infer.setScaledContents(False)
        self.image_label_infer.setBackgroundRole(QtGui.QPalette.Base)
        self.scroll_infer.setWidget(self.image_label_infer)
        # Original panel
        self.scroll_orig = QtWidgets.QScrollArea()
        self.scroll_orig.setWidgetResizable(True)
        self.image_label_orig = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.image_label_orig.setScaledContents(False)
        self.image_label_orig.setBackgroundRole(QtGui.QPalette.Base)
        self.scroll_orig.setWidget(self.image_label_orig)
        # Assemble side-by-side
        images_split.addWidget(self.scroll_infer)
        images_split.addWidget(self.scroll_orig)
        images_split.splitterMoved.connect(lambda *_: self.refresh_view())

        # Right: controls
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)

        # Active label column
        self.cmb_label_col = QtWidgets.QComboBox()
        self.cmb_label_col.currentTextChanged.connect(self.on_change_label_col)
        right_layout.addWidget(QtWidgets.QLabel("Active Label Column"))
        right_layout.addWidget(self.cmb_label_col)

        # Buttons for choices
        self.choice_buttons_container = QtWidgets.QWidget()
        self.choice_buttons_layout = QtWidgets.QGridLayout(self.choice_buttons_container)
        right_layout.addWidget(self.choice_buttons_container)

        # Dropdown for current row value
        right_layout.addWidget(QtWidgets.QLabel("Set label (dropdown)"))
        self.cmb_choice = QtWidgets.QComboBox()
        self.cmb_choice.currentTextChanged.connect(self.on_select_choice)
        right_layout.addWidget(self.cmb_choice)

        # Add new label column UI
        grp_add = QtWidgets.QGroupBox("Add Label Column")
        add_layout = QtWidgets.QFormLayout(grp_add)
        self.edt_new_col = QtWidgets.QLineEdit()
        self.edt_new_opts = QtWidgets.QLineEdit()
        self.btn_add_col = QtWidgets.QPushButton("Add")
        self.btn_add_col.clicked.connect(self.on_add_column)
        add_layout.addRow("Column name", self.edt_new_col)
        add_layout.addRow("Options (comma)", self.edt_new_opts)
        add_layout.addRow(self.btn_add_col)
        right_layout.addWidget(grp_add)

        # Filter / Sort
        grp_filter = QtWidgets.QGroupBox("Filter / Sort")
        fl = QtWidgets.QGridLayout(grp_filter)
        self.cmb_origin = QtWidgets.QComboBox()
        self.edt_text = QtWidgets.QLineEdit()
        self.chk_unlabeled = QtWidgets.QCheckBox("Only unlabeled (active col)")
        self.cmb_label_state = QtWidgets.QComboBox()
        self.cmb_label_state.addItems(["All", "Labeled", "Unlabeled"])  # stronger label filter
        self.cmb_sort_col = QtWidgets.QComboBox()
        self.chk_sort_desc = QtWidgets.QCheckBox("Desc")
        self.btn_apply_filter = QtWidgets.QPushButton("Apply")
        self.btn_reset_filter = QtWidgets.QPushButton("Reset")
        self.btn_apply_filter.clicked.connect(self.apply_filters)
        self.btn_reset_filter.clicked.connect(self.reset_filters)
        fl.addWidget(QtWidgets.QLabel("origin_class"), 0, 0)
        fl.addWidget(self.cmb_origin, 0, 1)
        fl.addWidget(QtWidgets.QLabel("Text contains"), 1, 0)
        fl.addWidget(self.edt_text, 1, 1)
        fl.addWidget(QtWidgets.QLabel("Label state"), 2, 0)
        fl.addWidget(self.cmb_label_state, 2, 1)
        fl.addWidget(self.chk_unlabeled, 3, 0, 1, 2)
        fl.addWidget(QtWidgets.QLabel("Sort by"), 4, 0)
        fl.addWidget(self.cmb_sort_col, 4, 1)
        fl.addWidget(self.chk_sort_desc, 4, 2)
        fl.addWidget(self.btn_apply_filter, 5, 1)
        fl.addWidget(self.btn_reset_filter, 5, 2)
        right_layout.addWidget(grp_filter)

        # Quick list of filtered items
        self.list_preview = QtWidgets.QListWidget()
        self.list_preview.itemSelectionChanged.connect(self.on_list_select)
        right_layout.addWidget(self.list_preview)

        # View options
        self.chk_fit = QtWidgets.QCheckBox("Fit to window")
        self.chk_fit.setChecked(True)
        self.chk_fit.toggled.connect(lambda *_: self.on_fit_toggle())
        right_layout.addWidget(self.chk_fit)

        # Live stats
        self.lbl_stats = QtWidgets.QLabel("")
        right_layout.addWidget(self.lbl_stats)

        # Summary (overall dataset)
        grp_sum = QtWidgets.QGroupBox("Summary")
        sum_layout = QtWidgets.QVBoxLayout(grp_sum)
        self.txt_summary = QtWidgets.QPlainTextEdit(readOnly=True)
        self.txt_summary.setMinimumHeight(140)
        sum_layout.addWidget(self.txt_summary)
        right_layout.addWidget(grp_sum)

        # Log bar at bottom
        grp_log = QtWidgets.QGroupBox("Log")
        log_layout = QtWidgets.QVBoxLayout(grp_log)
        self.txt_log = QtWidgets.QPlainTextEdit(readOnly=True)
        self.txt_log.setMinimumHeight(80)
        log_layout.addWidget(self.txt_log)
        right_layout.addWidget(grp_log)

        # Bookmark + Memo
        grp_bm = QtWidgets.QGroupBox("Bookmark / Memo")
        bm_layout = QtWidgets.QGridLayout(grp_bm)
        self.btn_toggle_bm = QtWidgets.QPushButton("★ Toggle Bookmark")
        self.btn_toggle_bm.clicked.connect(self.on_toggle_bookmark)
        self.edt_memo = QtWidgets.QPlainTextEdit()
        self.edt_memo.setPlaceholderText("Enter memo for this row…")
        self.btn_save_memo = QtWidgets.QPushButton("Save Memo")
        self.btn_save_memo.clicked.connect(self.on_save_memo)
        bm_layout.addWidget(self.btn_toggle_bm, 0, 0)
        bm_layout.addWidget(self.btn_save_memo, 0, 1)
        bm_layout.addWidget(self.edt_memo, 1, 0, 1, 2)
        right_layout.addWidget(grp_bm)

        # Navigation
        nav_layout = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("◀ Prev")
        self.btn_next = QtWidgets.QPushButton("Next ▶")
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        right_layout.addLayout(nav_layout)

        # Info
        self.lbl_info = QtWidgets.QLabel("")
        self.lbl_info.setWordWrap(True)
        right_layout.addWidget(self.lbl_info)
        right_layout.addStretch()

        splitter.addWidget(images_split)
        splitter.addWidget(right)
        splitter.setSizes([1200, 400])

        # Update on viewport resize for responsive fit
        self.scroll_infer.viewport().installEventFilter(self)
        self.scroll_orig.viewport().installEventFilter(self)

    def _connect_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self, activated=self.on_prev)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), self, activated=self.on_next)
        # Number keys to assign labels
        for i in range(1, 10):
            QtGui.QShortcut(QtGui.QKeySequence(str(i)), self, activated=lambda i=i: self.on_assign_index(i - 1))

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Resize and getattr(self, 'fit_to_window', True):
            self.refresh_view()
        return super().eventFilter(obj, event)

    def on_fit_toggle(self) -> None:
        self.fit_to_window = self.chk_fit.isChecked()
        self.refresh_view()

    # Data loading / configuration
    def on_open_excel(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Excel/CSV", os.getcwd(), "Excel/CSV (*.xlsx *.csv)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                self.df = pd.read_csv(path, encoding="utf-8-sig")
                self.sheet_name = "inference_results"
                # Create a working xlsx path next to csv
                xlsx_path = os.path.splitext(path)[0] + ".xlsx"
                with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                    self.df.to_excel(writer, index=False, sheet_name=self.sheet_name)
                self.excel_path = xlsx_path
            else:
                # Read first sheet name
                xl = pd.ExcelFile(path)
                self.sheet_name = xl.sheet_names[0]
                self.df = xl.parse(self.sheet_name)
                self.excel_path = path
            # Defaults
            self.output_excel_path = os.path.splitext(self.excel_path)[0] + "_labeled.xlsx"
            self.json_path = default_json_path(self.output_excel_path)
            # Ensure label columns
            if self.df is not None:
                for col in self.label_map.keys():
                    if col not in self.df.columns:
                        self.df[col] = ""
                    ensure_object_dtype(self.df, col)
                # Merge previous JSON labels into DataFrame (resume work)
                try:
                    merge_json_into_df(self.json_path, self.df, list(self.label_map.keys()))
                except Exception:
                    pass
                # Determine or add label columns in workbook later on export
            self.filtered_indices = list(self.df.index) if self.df is not None else []
            self.current_idx = 0
            # Build label controls and filter controls
            self.refresh_label_controls()
            self.populate_filter_controls()
            # Default filter: origin_class=(all), label state=Unlabeled, sort by img_path if exists
            # Set label state selector
            try:
                idx = self.cmb_label_state.findText("Unlabeled")
                if idx >= 0:
                    self.cmb_label_state.setCurrentIndex(idx)
            except Exception:
                pass
            # Set default sort column
            if self.cmb_sort_col.count() > 0:
                pref = "img_path" if (self.df is not None and "img_path" in self.df.columns) else ("filename" if (self.df is not None and "filename" in self.df.columns) else None)
                if pref is not None:
                    i2 = self.cmb_sort_col.findText(pref)
                    if i2 >= 0:
                        self.cmb_sort_col.setCurrentIndex(i2)
            # Apply filters to drive the list and navigation
            self.apply_filters()
            self.refresh_view()
            self.status.showMessage(f"Loaded: {self.excel_path}")
            self.log(f"Loaded file: {self.excel_path}")
            # persist
            self.settings.setValue("excel_path", path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Open failed", str(e))

    def on_set_images_base(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Images Base", os.getcwd())
        if path:
            self.images_base = path
            self.refresh_view()
            self.log(f"Set Images Base: {path}")
            self.settings.setValue("images_base", path)

    def on_set_images_base_orig(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Original Images Base", os.getcwd())
        if path:
            self.images_base_orig = path
            self.refresh_view()
            self.log(f"Set Original Images Base: {path}")
            self.settings.setValue("images_base_orig", path)

    def restore_last_session(self) -> None:
        excel = self.settings.value("excel_path", "", str)
        img_base = self.settings.value("images_base", "", str)
        img_base_orig = self.settings.value("images_base_orig", "", str)
        if excel and os.path.exists(excel):
            # Reuse same loading routine
            try:
                self.on_open_excel.__func__(self)  # fallback if needed
            except Exception:
                self.load_excel_from_path(excel) if hasattr(self, 'load_excel_from_path') else None
        if img_base and os.path.isdir(img_base):
            self.images_base = img_base
        if img_base_orig and os.path.isdir(img_base_orig):
            self.images_base_orig = img_base_orig
        if img_base or img_base_orig:
            self.refresh_view()

    def on_configure_labels(self) -> None:
        text, ok = QtWidgets.QInputDialog.getMultiLineText(
            self,
            "Configure Labels",
            "One line per column: name: opt1, opt2, ...",
            "review_label: OK, NG, 보류\npriority: High, Medium, Low",
        )
        if not ok:
            return
        mapping: Dict[str, List[str]] = {}
        for line in text.splitlines():
            if ":" in line:
                name, vals = line.split(":", 1)
                name = name.strip()
                opts = [v.strip() for v in vals.split(",") if v.strip()]
                if name:
                    mapping[name] = opts
        if mapping:
            self.label_map = mapping
            self.active_label_col = list(self.label_map.keys())[0]
            if self.df is not None:
                for col in self.label_map.keys():
                    if col not in self.df.columns:
                        self.df[col] = ""
                    ensure_object_dtype(self.df, col)
            self.refresh_label_controls()
            self.refresh_view()

    def on_add_column(self) -> None:
        name = self.edt_new_col.text().strip()
        opts = [v.strip() for v in self.edt_new_opts.text().split(',') if v.strip()]
        if not name or not opts:
            QtWidgets.QMessageBox.information(self, "Add Column", "Enter column name and at least one option.")
            return
        self.label_map[name] = opts
        self.active_label_col = name
        if self.df is not None:
            if name not in self.df.columns:
                self.df[name] = ""
            ensure_object_dtype(self.df, name)
        self.refresh_label_controls()
        self.refresh_view()
        self.status.showMessage(f"Added label column: {name}")

    def on_matching_test(self) -> None:
        if self.df is None or self.df.empty:
            QtWidgets.QMessageBox.information(self, "Matching Test", "Open Excel/CSV first.")
            return
        if not self.images_base:
            QtWidgets.QMessageBox.information(self, "Matching Test", "Set Images Base first.")
            return
        total_available = len(self.filtered_indices) if self.filtered_indices else len(self.df)
        default_n = min(200, total_available) if total_available > 0 else 0
        n, ok = QtWidgets.QInputDialog.getInt(self, "Matching Test", "Sample size", default_n, 1, max(1, total_available), 1)
        if not ok:
            return
        if n <= 0 or total_available == 0:
            QtWidgets.QMessageBox.information(self, "Matching Test", "No rows to test.")
            return
        indices = self.filtered_indices if self.filtered_indices else list(self.df.index)
        sample = indices[:n]
        ok_count = 0
        misses: List[str] = []
        for ridx in sample:
            r = self.df.loc[ridx]
            p = str(r.get("img_path", "")) or str(r.get("filename", ""))
            rp = resolve_image_path(self.images_base, p)
            if rp and os.path.exists(rp):
                ok_count += 1
            else:
                if len(misses) < 10:
                    misses.append(p)
        rate = (ok_count / float(len(sample))) * 100.0
        msg = f"Matched {ok_count}/{len(sample)} ({rate:.1f}%)"
        if misses:
            msg += "\n\nExamples not found:" + "\n- " + "\n- ".join(misses)
        QtWidgets.QMessageBox.information(self, "Matching Test", msg)

    # Export JSON → Excel
    def on_apply_json(self) -> None:
        if not (self.excel_path and is_xlsx(self.excel_path)):
            QtWidgets.QMessageBox.warning(self, "Export", "Open a valid Excel/CSV first.")
            return
        out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save labeled Excel", self.output_excel_path, "Excel (*.xlsx)")
        if not out:
            return
        try:
            # Ensure workbook has all label columns and get indices
            wb = load_workbook(self.excel_path)
            ws = wb[self.sheet_name]
            headers = [c.value for c in ws[1]]
            if headers is None:
                headers = []
            col_indices: Dict[str, int] = {}
            for col in self.label_map.keys():
                if col in headers:
                    col_indices[col] = headers.index(col) + 1
                else:
                    headers.append(col)
                    idx = len(headers)
                    ws.cell(row=1, column=idx, value=col)
                    col_indices[col] = idx
            wb.save(out)
            wb.close()
            # Apply JSON into the new file
            applied = apply_json_to_excel(self.json_path or default_json_path(out), out, self.sheet_name, col_indices, self.df)
            self.output_excel_path = out
            self.status.showMessage(f"Applied {applied} cells → {out}")
            self.log(f"Applied JSON to Excel: {applied} cells → {out}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export failed", str(e))

    # Navigation / labeling
    def on_prev(self) -> None:
        if not self.filtered_indices:
            return
        self.current_idx = max(0, self.current_idx - 1)
        self.refresh_view()

    def on_next(self) -> None:
        if not self.filtered_indices:
            return
        self.current_idx = min(len(self.filtered_indices) - 1, self.current_idx + 1)
        self.refresh_view()

    def on_assign_index(self, choice_index: int) -> None:
        if not (self.df is not None and self.filtered_indices):
            return
        opts = self.label_map.get(self.active_label_col, [])
        if not (0 <= choice_index < len(opts)):
            return
        value = opts[choice_index]
        row_idx = self.filtered_indices[self.current_idx]
        # Save to JSON immediately
        row = self.df.loc[row_idx]
        keys_for_row = {"img_path": str(row.get("img_path", "")), "filename": str(row.get("filename", ""))}
        json_path = self.json_path or default_json_path(self.output_excel_path or self.excel_path)
        store = load_label_store(json_path)
        key = str(row_idx)
        entry = store["labels"].get(key) or {}
        for k, v in keys_for_row.items():
            entry[k] = v
        values = entry.get("values") or {}
        values[self.active_label_col] = value
        entry["values"] = values
        store["labels"][key] = entry
        save_label_store(json_path, store)
        self.status.showMessage(f"Saved to JSON: {self.active_label_col}={value}")
        self.log(f"Label saved: row {row_idx} {self.active_label_col}={value}")
        # Auto next
        self.on_next()

    def on_select_choice(self, text: str) -> None:
        if not text or text == "Select…":
            return
        # Map dropdown selection to save
        if self.df is None or not self.filtered_indices:
            return
        row_idx = self.filtered_indices[self.current_idx]
        row = self.df.loc[row_idx]
        keys_for_row = {"img_path": str(row.get("img_path", "")), "filename": str(row.get("filename", ""))}
        json_path = self.json_path or default_json_path(self.output_excel_path or self.excel_path)
        store = load_label_store(json_path)
        key = str(row_idx)
        entry = store["labels"].get(key) or {}
        for k, v in keys_for_row.items():
            entry[k] = v
        values = entry.get("values") or {}
        values[self.active_label_col] = text
        entry["values"] = values
        store["labels"][key] = entry
        save_label_store(json_path, store)
        self.status.showMessage(f"Saved to JSON: {self.active_label_col}={text}")
        self.log(f"Label saved: row {row_idx} {self.active_label_col}={text}")
        self.on_next()

    def on_change_label_col(self, name: str) -> None:
        if name:
            self.active_label_col = name
            self.refresh_label_controls()
            self.populate_filter_controls()

    def refresh_label_controls(self) -> None:
        # Reset combobox
        self.cmb_label_col.blockSignals(True)
        self.cmb_label_col.clear()
        for name in self.label_map.keys():
            self.cmb_label_col.addItem(name)
        idx = list(self.label_map.keys()).index(self.active_label_col) if self.active_label_col in self.label_map else 0
        self.cmb_label_col.setCurrentIndex(idx)
        self.cmb_label_col.blockSignals(False)
        # Rebuild choice buttons (1..n shortcuts)
        while self.choice_buttons_layout.count():
            item = self.choice_buttons_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        opts = self.label_map.get(self.active_label_col, [])
        for i, opt in enumerate(opts):
            btn = QtWidgets.QPushButton(f"{i+1}. {opt}")
            btn.clicked.connect(lambda _, j=i: self.on_assign_index(j))
            self.choice_buttons_layout.addWidget(btn, i // 3, i % 3)
        # Update dropdown options
        self.cmb_choice.blockSignals(True)
        self.cmb_choice.clear()
        self.cmb_choice.addItem("Select…")
        for opt in opts:
            self.cmb_choice.addItem(opt)
        self.cmb_choice.setCurrentIndex(0)
        self.cmb_choice.blockSignals(False)

    def populate_filter_controls(self) -> None:
        # origin_class dropdown
        self.cmb_origin.blockSignals(True)
        self.cmb_origin.clear()
        self.cmb_origin.addItem("(all)")
        if self.df is not None and "origin_class" in self.df.columns:
            try:
                # Use unique values from the full dataframe, not filtered
                vals = pd.Series(self.df["origin_class"].astype(str)).dropna().unique().tolist()
                for v in sorted([str(x) for x in vals]):
                    self.cmb_origin.addItem(v)
            except Exception:
                pass
        self.cmb_origin.setCurrentIndex(0)
        self.cmb_origin.blockSignals(False)
        # Sort columns
        self.cmb_sort_col.blockSignals(True)
        self.cmb_sort_col.clear()
        if self.df is not None:
            for col in list(self.df.columns):
                self.cmb_sort_col.addItem(col)
        self.cmb_sort_col.blockSignals(False)

    def apply_filters(self) -> None:
        if self.df is None:
            return
        df = self.df.copy()
        # origin_class filter
        origin_sel = self.cmb_origin.currentText()
        if origin_sel and origin_sel != "(all)" and "origin_class" in df.columns:
            df = df[df["origin_class"].astype(str) == origin_sel]
        # text contains across img_path and pred
        t = self.edt_text.text().strip()
        if t:
            t_low = t.lower()
            mask = pd.Series(False, index=df.index)
            for col in ("img_path", "filename", "pred_seg_results"):
                if col in df.columns:
                    mask = mask | df[col].astype(str).str.lower().str.contains(t_low, na=False)
            df = df[mask]
        # label state filter
        state = self.cmb_label_state.currentText()
        if state == "Unlabeled" and self.active_label_col in df.columns:
            df = df[(df[self.active_label_col].isna()) | (df[self.active_label_col] == "")]
        elif state == "Labeled" and self.active_label_col in df.columns:
            df = df[(~df[self.active_label_col].isna()) & (df[self.active_label_col] != "")]
        # legacy checkbox support
        if self.chk_unlabeled.isChecked() and self.active_label_col in df.columns:
            df = df[(df[self.active_label_col].isna()) | (df[self.active_label_col] == "")]
        # sort
        sort_col = self.cmb_sort_col.currentText()
        if sort_col and sort_col in df.columns:
            df = df.sort_values(by=sort_col, ascending=not self.chk_sort_desc.isChecked(), kind="mergesort")
        # update indices/preview list
        self.filtered_indices = list(df.index)
        self.current_idx = 0 if self.filtered_indices else 0
        self.list_preview.blockSignals(True)
        self.list_preview.clear()
        for idx in self.filtered_indices[:1000]:  # cap preview
            row = self.df.loc[idx]
            disp = str(row.get("img_path", row.get("filename", idx)))
            label_val = str(row.get(self.active_label_col, "")) if self.active_label_col in self.df.columns else ""
            prefix = "✅" if label_val else "⏳"
            self.list_preview.addItem(f"{idx}: {prefix} {disp}")
        self.list_preview.blockSignals(False)
        # live stats (filtered + overall)
        total = len(self.df) if self.df is not None else 0
        overall_unlabeled = 0
        overall_labeled = 0
        if self.df is not None and self.active_label_col in self.df.columns:
            overall_unlabeled = int(((self.df[self.active_label_col].isna()) | (self.df[self.active_label_col] == "")).sum())
            overall_labeled = total - overall_unlabeled
        # filtered counts
        f_total = len(self.filtered_indices)
        f_labeled = 0
        f_unlabeled = 0
        if f_total > 0 and self.active_label_col in self.df.columns:
            sub = self.df.loc[self.filtered_indices, self.active_label_col]
            f_unlabeled = int(((sub.isna()) | (sub == "")).sum())
            f_labeled = f_total - f_unlabeled
        self.lbl_stats.setText(
            f"Filtered: {f_total} | Labeled: {f_labeled} | Unlabeled: {f_unlabeled}  ||  Overall: {total} (L:{overall_labeled} U:{overall_unlabeled})"
        )
        self.refresh_view()
        # Ensure current row is selected in the list for visibility
        try:
            if self.filtered_indices:
                sel_idx = self.filtered_indices[self.current_idx]
                for i in range(self.list_preview.count()):
                    if self.list_preview.item(i).text().startswith(f"{sel_idx}:"):
                        self.list_preview.setCurrentRow(i)
                        break
        except Exception:
            pass
        # Update summary after any filter change
        self.update_summary()

    def update_summary(self) -> None:
        if self.df is None or self.df.empty:
            self.txt_summary.setPlainText("No data loaded.")
            return
        total = len(self.df)
        labeled = 0
        unlabeled = 0
        if self.active_label_col in self.df.columns:
            unlabeled = int(((self.df[self.active_label_col].isna()) | (self.df[self.active_label_col] == "")).sum())
            labeled = total - unlabeled
        prog_pct = (labeled / total * 100.0) if total else 0.0
        # Label distribution (top 10)
        label_dist = []
        if self.active_label_col in self.df.columns:
            try:
                vc = self.df[self.active_label_col].fillna("").replace("", "(empty)").value_counts()
                for k, v in vc.head(10).items():
                    label_dist.append(f"  - {k}: {v}")
            except Exception:
                pass
        # origin_class distribution (top 10)
        origin_dist = []
        if "origin_class" in self.df.columns:
            try:
                vc2 = self.df["origin_class"].astype(str).value_counts()
                for k, v in vc2.head(10).items():
                    origin_dist.append(f"  - {k}: {v}")
            except Exception:
                pass
        lines = [
            f"Total: {total}",
            f"Labeled: {labeled} | Unlabeled: {unlabeled} | Progress: {prog_pct:.1f}%",
            "",
            f"Active label: {self.active_label_col}",
            "Label distribution (top 10):",
            *label_dist,
            "",
            "origin_class distribution (top 10):",
            *origin_dist,
        ]
        self.txt_summary.setPlainText("\n".join(lines))

    def log(self, message: str) -> None:
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, 'txt_log') and self.txt_log is not None:
                self.txt_log.appendPlainText(f"[{ts}] {message}")
        except Exception:
            pass

    def reset_filters(self) -> None:
        if self.df is None:
            return
        self.edt_text.clear()
        self.chk_unlabeled.setChecked(False)
        self.cmb_origin.setCurrentIndex(0)
        self.cmb_sort_col.setCurrentIndex(0 if self.cmb_sort_col.count() > 0 else -1)
        self.chk_sort_desc.setChecked(False)
        self.filtered_indices = list(self.df.index)
        self.current_idx = 0
        self.list_preview.clear()
        self.refresh_view()

    def on_list_select(self) -> None:
        items = self.list_preview.selectedItems()
        if not items:
            return
        # parse index prefix
        text = items[0].text()
        try:
            idx = int(text.split(":", 1)[0])
        except Exception:
            return
        if idx in self.filtered_indices:
            self.current_idx = self.filtered_indices.index(idx)
            self.refresh_view()

    def on_toggle_bookmark(self) -> None:
        if self.df is None or not self.filtered_indices:
            return
        row_idx = self.filtered_indices[self.current_idx]
        json_path = self.json_path or default_json_path(self.output_excel_path or self.excel_path)
        entry = get_json_entry(json_path, row_idx)
        curr = bool(entry.get("bookmark", False))
        upsert_json_entry(json_path, row_idx, {"bookmark": not curr})
        self.status.showMessage("Bookmark " + ("ON" if not curr else "OFF"))
        self.log(f"Bookmark {'ON' if not curr else 'OFF'} for row {row_idx}")

    def on_save_memo(self) -> None:
        if self.df is None or not self.filtered_indices:
            return
        row_idx = self.filtered_indices[self.current_idx]
        memo = self.edt_memo.toPlainText()
        json_path = self.json_path or default_json_path(self.output_excel_path or self.excel_path)
        upsert_json_entry(json_path, row_idx, {"memo": memo})
        self.status.showMessage("Memo saved")
        self.log(f"Memo saved for row {row_idx} ({len(memo)} chars)")

    def _resolve_img_for_row(self, row_idx: int) -> Tuple[Optional[str], Optional[str], str]:
        if self.df is None or self.images_base == "":
            return None, None, ""
        r = self.df.loc[row_idx]
        p = str(r.get("img_path", "")) or str(r.get("filename", ""))
        resolved_infer = resolve_image_path(self.images_base, p)
        # Resolve original using same relative path or basename match
        resolved_orig = None
        if self.images_base_orig:
            rel = normalize_relative_path(p)
            cand = os.path.join(self.images_base_orig, rel)
            if os.path.exists(cand):
                resolved_orig = cand
            else:
                base = os.path.basename(rel)
                base_no_ext, _ = os.path.splitext(base)
                for pattern in [
                    os.path.join(self.images_base_orig, "**", base),
                    os.path.join(self.images_base_orig, "**", f"{base_no_ext}.*"),
                ]:
                    m = glob.glob(pattern, recursive=True)
                    if m:
                        resolved_orig = m[0]
                        break
        return resolved_infer, resolved_orig, p

    def refresh_view(self) -> None:
        if self.df is None or not self.filtered_indices:
            self.image_label_infer.setPixmap(QtGui.QPixmap())
            self.image_label_orig.setPixmap(QtGui.QPixmap())
            self.lbl_info.setText("Open Excel/CSV and set Images Bases.")
            return
        row_idx = self.filtered_indices[self.current_idx]
        resolved_infer, resolved_orig, disp = self._resolve_img_for_row(row_idx)
        self._set_image_on_label(self.image_label_infer, self.scroll_infer, resolved_infer)
        self._set_image_on_label(self.image_label_orig, self.scroll_orig, resolved_orig)
        self.lbl_info.setText(
            f"Row {self.current_idx+1}/{len(self.filtered_indices)}\nINF: {'OK' if resolved_infer else 'not found'} | ORG: {'OK' if resolved_orig else 'not found'}\n{disp}"
        )
        # Load memo for current row
        json_path = self.json_path or default_json_path(self.output_excel_path or self.excel_path)
        entry = get_json_entry(json_path, row_idx)
        self.edt_memo.blockSignals(True)
        self.edt_memo.setPlainText(str(entry.get("memo", "")))
        self.edt_memo.blockSignals(False)

    def _set_image_on_label(self, label: QtWidgets.QLabel, scroll: QtWidgets.QScrollArea, path: Optional[str]) -> None:
        if not path or not os.path.exists(path):
            label.setPixmap(QtGui.QPixmap())
            return
        if not getattr(self, 'fit_to_window', True):
            label.setPixmap(QtGui.QPixmap(path))
            return
        vp_size = scroll.viewport().size()
        if vp_size.width() <= 0 or vp_size.height() <= 0:
            label.setPixmap(QtGui.QPixmap(path))
            return
        pix = QtGui.QPixmap(path)
        scaled = pix.scaled(vp_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        label.setPixmap(scaled)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = LabelerWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


