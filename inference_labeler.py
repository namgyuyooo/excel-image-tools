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

from openpyxl import load_workbook

# Reuse path resolution from the existing module
from create_excel_from_seg_csv import resolve_image_path

# Hardcoded paths for specific inference results
INFERENCE_CSV_PATH = "/Users/yunamgyu/Downloads/v0.5/v0.5_inference_20250818_v0.2/inference_results.csv"
IMAGES_BASE_PATH = "/Users/yunamgyu/Downloads/v0.5/v0.5_inference_20250818_v0.2/images"

# Memory management utilities
def get_memory_usage():
    """Get current memory usage in MB"""
    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except:
        return 0

def check_memory_limit(limit_mb=1024):
    """Check if memory usage exceeds limit"""
    return get_memory_usage() > limit_mb

def force_garbage_collection():
    """Force garbage collection to free memory"""
    gc.collect()

def get_system_memory():
    """Get total system memory in MB"""
    try:
        return psutil.virtual_memory().total / 1024 / 1024
    except:
        return 8192  # Default to 8GB if can't detect


def parse_pred_list(value) -> List[str]:
    """Parse pred_seg_results value into a list of strings.
    Handles JSON arrays, python-like list strings, or comma-separated strings.
    """
    try:
        if isinstance(value, (list, tuple, set)):
            return [str(x).strip() for x in value]
        s = str(value).strip()
        if not s:
            return []
        # Try JSON first
        if s.startswith("[") or s.startswith("{"):
            try:
                data = json.loads(s)
                if isinstance(data, (list, tuple, set)):
                    return [str(x).strip() for x in data]
            except Exception:
                pass
        # Fallback: strip brackets and split by semicolon/comma variants
        s2 = s.strip().strip('[](){}')
        parts = [p.strip().strip("'\"") for p in re.split(r"[;,\uFF1B\uFF0C]+", s2) if p.strip()]
        return parts
    except Exception:
        return []


def ensure_object_dtype(df: pd.DataFrame, column: str) -> None:
    try:
        df[column] = df[column].astype("object")
    except Exception:
        pass


def default_json_path(xlsx_path: str) -> str:
    base = os.path.basename(xlsx_path)
    root, _ = os.path.splitext(base)
    parent = os.path.dirname(xlsx_path) or os.getcwd()
    # Preferred naming: if Excel is *_labeled.xlsx → JSON is *_labels.json
    if root.endswith("_labeled"):
        new_root = root[: -len("_labeled")] + "_labels"
    else:
        new_root = root + "_labels"
    new_path = os.path.join(parent, f"{new_root}.json")
    # Legacy path compatibility: previously always appended _labels
    legacy_path = os.path.join(parent, f"{root}_labels.json")
    # If legacy exists and new doesn't, keep using legacy for seamless migration
    if os.path.exists(legacy_path) and not os.path.exists(new_path):
        return legacy_path
    return new_path


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


def save_label_store(json_path: str, store: dict) -> bool:
    """Atomically persist the label store. Returns True on success."""
    try:
        store["updated_at"] = datetime.now(_UTC).isoformat()
        tmp = json_path + ".tmp"
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
        os.replace(tmp, json_path)
        return True
    except Exception:
        return False


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
                    curr = None
                    try:
                        curr = df.at[ridx, col]
                    except Exception:
                        curr = None
                    is_empty = (curr is None) or (str(curr) == "")
                    try:
                        if not is_empty:
                            is_empty = bool(pd.isna(curr))
                    except Exception:
                        pass
                    if is_empty:
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


class InferenceLabelerWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("추론 결과 라벨링 도구")
        self.resize(1400, 900)

        # Fixed paths for this specific tool
        self.csv_path: str = INFERENCE_CSV_PATH
        self.images_base: str = IMAGES_BASE_PATH
        
        # State
        self.df: Optional[pd.DataFrame] = None
        self.json_path: str = ""
        self.col_indices: Dict[str, int] = {}
        
        # Memory management and performance settings - optimized for 50k+ records
        system_memory = get_system_memory()
        self.max_memory_mb = min(2048, system_memory * 0.3)  # Increased for large datasets
        self.chunk_size = 1000  # Increased chunk size
        self.max_table_rows = 200  # Reduced for better performance
        self.image_cache_size = 12  # Increased for better performance and faster navigation
        self._image_cache: Dict[str, QtGui.QPixmap] = {}
        self._lazy_loading = True
        
        # Performance optimization flags
        self._filter_cache: Optional[pd.Series] = None
        self._last_filter_hash: Optional[str] = None
        
        # Unified labeling approach - single active column with as-is/to-be integration
        self.active_label_col: str = "review_label"
        self.label_choices: List[str] = [
            "OK",
            "애매한 OK", 
            "NG", 
            "애매한 NG",
            "보류",
        ]
        
        self.current_idx: int = 0
        self.filtered_indices: List[int] = []
        self.fit_to_window: bool = True
        self.tobe_choices: List[str] = [
            "돌기",
            "흑점", 
            "색상얼룩",
            "찍힘",
            "SR이물",
            "SR금속",
        ]
        
        # pred_seg_results filter choices
        self.pred_filter_choices: List[str] = []
        self.selected_pred_filters: set = set()
        self.pred_filter_checkboxes: Dict[str, QtWidgets.QCheckBox] = {}
        
        # Auto-advance settings
        self.auto_advance_enabled: bool = True
        
        # AS-IS/TO-BE mode settings
        self.as_is_tobe_mode: bool = False
        

        
        # Performance monitoring
        self._label_count = 0
        self._session_start_time = datetime.now()
        
        # Settings and navigation
        self.settings = QtCore.QSettings("rtm", "inference_labeler")
        self._navigating: bool = False
        
        # Batched JSON save - optimized for large datasets
        self._pending_ops: List[Tuple[str, int, Dict[str, object], Dict[str, str]]] = []
        self._pending_json_path: str = ""
        self._save_timer = QtCore.QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)  # Reduced to 500ms for faster response
        self._save_timer.timeout.connect(self._flush_pending_ops)
        
        # Performance optimization settings
        self._ui_update_throttle = QtCore.QTimer(self)
        self._ui_update_throttle.setSingleShot(True)
        self._ui_update_throttle.setInterval(50)  # Reduced to 50ms for faster UI updates
        self._ui_update_throttle.timeout.connect(self._deferred_ui_update)
        self._pending_ui_update = False
        
        # Periodic session saving
        self._session_save_timer = QtCore.QTimer(self)
        self._session_save_timer.timeout.connect(self.save_session_state)
        self._session_save_timer.start(60000)  # Save every 60 seconds for better performance
        
        # Performance optimization flags
        self._last_table_update = 0
        self._table_update_throttle = 100  # Reduced to 100ms between table updates
        self._last_image_path = ""
        self._image_update_throttle = 200  # Increased to 200ms between image updates

        # UI
        self._build_ui()
        self._connect_shortcuts()
        
        # Auto-load the data
        self._auto_load_data()
        
        # Try restore last session after data is loaded
        QtCore.QTimer.singleShot(500, self.restore_session_state)

    def _auto_load_data(self):
        """Automatically load the CSV data on startup"""
        if os.path.exists(self.csv_path):
            self.load_csv_data()
        else:
            self.status.showMessage(f"CSV 파일을 찾을 수 없음: {self.csv_path}")

    def _build_ui(self) -> None:
        self.status = self.statusBar()
        
        # Create status bar widgets for real-time information
        self._create_status_widgets()

        # Apply modern theme


        # Create modern toolbar
        self._create_toolbar()

        # Menus
        file_menu = self.menuBar().addMenu("파일")
        act_reload = file_menu.addAction("데이터 새로고침")
        act_export = file_menu.addAction("라벨을 엑셀로 내보내기")
        file_menu.addSeparator()
        act_save_session = file_menu.addAction("세션 상태 저장")
        act_load_session = file_menu.addAction("세션 상태 복원")
        file_menu.addSeparator()
        act_quit = file_menu.addAction("종료")
        
        act_quit.triggered.connect(self.close)
        act_reload.triggered.connect(self.load_csv_data)
        act_export.triggered.connect(self.on_export_labels)
        act_save_session.triggered.connect(self.save_session_state)
        act_load_session.triggered.connect(self.restore_session_state)

        # Memory management menu
        memory_menu = self.menuBar().addMenu("메모리")
        act_clear_cache = memory_menu.addAction("이미지 캐시 삭제")
        act_clear_cache.triggered.connect(self._clear_image_cache)
        act_memory_info = memory_menu.addAction("메모리 정보")
        act_memory_info.triggered.connect(self._show_memory_info)
        act_force_cleanup = memory_menu.addAction("메모리 정리")
        act_force_cleanup.triggered.connect(self._force_memory_cleanup)
        act_performance_stats = memory_menu.addAction("성능 통계")
        act_performance_stats.triggered.connect(self._show_performance_stats)

        # Central splitter - 3 column layout
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.setCentralWidget(splitter)

        # Column 1: Image preview
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.image_label.setScaledContents(False)
        self.image_label.setBackgroundRole(QtGui.QPalette.Base)
        self.scroll_area.setWidget(self.image_label)
        self.path_label = QtWidgets.QLabel("")
        self.path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.path_label.setWordWrap(True)

        
        image_panel = QtWidgets.QWidget()
        image_layout = QtWidgets.QVBoxLayout(image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(2)
        image_layout.addWidget(self.scroll_area)
        image_layout.addWidget(self.path_label)
        
        # Image panel only contains image and path
        image_layout.addWidget(self.scroll_area)
        image_layout.addWidget(self.path_label)

        # Column 2: Controls and labeling
        controls_panel = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls_panel)
        controls_layout.setSpacing(3)  # Reduced spacing between sections
        controls_layout.setContentsMargins(3, 3, 3, 3)  # Reduced margins

        # Progress dashboard
        progress_dashboard = self._create_progress_dashboard()
        controls_layout.addWidget(progress_dashboard)

        # Current row info
        self.lbl_current_info = QtWidgets.QLabel("데이터가 로드되지 않음")
        controls_layout.addWidget(self.lbl_current_info)

        # Bookmark and memo section moved to column 2
        grp_bookmark_memo = QtWidgets.QGroupBox("북마크")
        bookmark_memo_layout = QtWidgets.QVBoxLayout(grp_bookmark_memo)
        bookmark_memo_layout.setContentsMargins(5, 5, 5, 5)
        bookmark_memo_layout.setSpacing(5)
        
        # Bookmark controls
        bookmark_controls = QtWidgets.QHBoxLayout()
        self.btn_toggle_bookmark = QtWidgets.QPushButton("북마크 토글 (B)")
        self.btn_toggle_bookmark.clicked.connect(self.toggle_bookmark)
        self.lbl_bookmark_status = QtWidgets.QLabel("북마크: ❌")
        bookmark_controls.addWidget(self.btn_toggle_bookmark)
        bookmark_controls.addWidget(self.lbl_bookmark_status)
        bookmark_controls.addStretch()
        bookmark_memo_layout.addLayout(bookmark_controls)
        

        
        controls_layout.addWidget(grp_bookmark_memo)

        # Quick labeling section with collapsible UI
        grp_labeling = QtWidgets.QGroupBox()
        labeling_main_layout = QtWidgets.QVBoxLayout(grp_labeling)
        
        # Toggle button for quick labeling
        # Section title for quick labeling
        labeling_title = QtWidgets.QLabel("빠른 라벨링")
        labeling_main_layout.addWidget(labeling_title)
        
        # Quick labeling container with compact layout
        self.quick_labeling_container = QtWidgets.QWidget()
        quick_labeling_layout = QtWidgets.QVBoxLayout(self.quick_labeling_container)
        quick_labeling_layout.setSpacing(2)  # Reduce spacing
        quick_labeling_layout.setContentsMargins(5, 2, 5, 2)  # Reduce margins
        
        # Create scrollable area for buttons
        self.choice_buttons_scroll = QtWidgets.QScrollArea()
        self.choice_buttons_scroll.setWidgetResizable(True)
        self.choice_buttons_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.choice_buttons_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        
        self.choice_buttons_container = QtWidgets.QWidget()
        self.choice_buttons_layout = QtWidgets.QGridLayout(self.choice_buttons_container)
        self.choice_buttons_layout.setSpacing(4)  # Normal spacing
        self.choice_buttons_layout.setContentsMargins(4, 4, 4, 4)
        
        self.choice_buttons_scroll.setWidget(self.choice_buttons_container)
        quick_labeling_layout.addWidget(self.choice_buttons_scroll)
        
        labeling_main_layout.addWidget(self.quick_labeling_container)
        
        # Set size constraints for quick labeling section
        grp_labeling.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        # Set scroll area height
        self.choice_buttons_scroll.setMinimumHeight(100)
        
        controls_layout.addWidget(grp_labeling)

        # AS-IS / TO-BE mapping panel with collapsible UI
        grp_as_is_tobe = QtWidgets.QGroupBox()
        as_is_tobe_main_layout = QtWidgets.QVBoxLayout(grp_as_is_tobe)
        
        # Toggle button for AS-IS/TO-BE
        # Section title for AS-IS/TO-BE
        as_is_tobe_title = QtWidgets.QLabel("AS-IS → TO-BE 라벨링")
        as_is_tobe_main_layout.addWidget(as_is_tobe_title)
        
        # AS-IS/TO-BE container
        self.as_is_tobe_container = QtWidgets.QWidget()
        self.as_is_tobe_layout = QtWidgets.QGridLayout(self.as_is_tobe_container)
        self.as_is_tobe_layout.setSpacing(5)
        self.as_is_tobe_layout.setContentsMargins(5, 5, 5, 5)
        
        # Initially hide AS-IS/TO-BE container
        self.as_is_tobe_container.setVisible(False)
        
        as_is_tobe_main_layout.addWidget(self.as_is_tobe_container)
        
        # Set size constraints for AS-IS/TO-BE section
        grp_as_is_tobe.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        controls_layout.addWidget(grp_as_is_tobe)

        # Filter controls with collapsible sections
        grp_filter = QtWidgets.QGroupBox("필터 / 탐색")
        grp_filter_layout = QtWidgets.QVBoxLayout(grp_filter)
        
        # Quick filter buttons
        quick_filter_widget = self._create_quick_filters()
        grp_filter_layout.addWidget(quick_filter_widget)
        
        # Basic filters toggle button
        # Section title for basic filters
        basic_filters_title = QtWidgets.QLabel("기본 필터")
        grp_filter_layout.addWidget(basic_filters_title)
        
        # Basic filters container with compact layout
        self.basic_filters_widget = QtWidgets.QWidget()
        fl = QtWidgets.QGridLayout(self.basic_filters_widget)
        fl.setSpacing(3)  # Reduce spacing
        fl.setContentsMargins(5, 2, 5, 2)  # Reduce margins
        
        self.chk_unlabeled = QtWidgets.QCheckBox("라벨 없는 항목만")
        self.cmb_label_state = QtWidgets.QComboBox()
        self.cmb_label_state.addItems(["전체", "라벨됨", "라벨안됨"])
        self.cmb_label_value = QtWidgets.QComboBox()
        self.cmb_model_name = QtWidgets.QComboBox()
        self.chk_bookmarks = QtWidgets.QCheckBox("북마크만")
        
        fl.addWidget(self.chk_unlabeled, 0, 0)
        fl.addWidget(self.cmb_label_state, 0, 1)
        fl.addWidget(QtWidgets.QLabel("라벨 값:"), 1, 0)
        fl.addWidget(self.cmb_label_value, 1, 1)
        fl.addWidget(QtWidgets.QLabel("모델명:"), 2, 0)
        fl.addWidget(self.cmb_model_name, 2, 1)
        fl.addWidget(self.chk_bookmarks, 3, 0)
        
        grp_filter_layout.addWidget(self.basic_filters_widget)
        
        # Set size constraints for filter section
        grp_filter.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        controls_layout.addWidget(grp_filter)

        # pred_seg_results filter section with collapsible UI
        grp_pred_filter = QtWidgets.QGroupBox()
        pred_filter_main_layout = QtWidgets.QVBoxLayout(grp_pred_filter)
        
        # Toggle button for pred filters
        # Section title for prediction filters
        pred_filters_title = QtWidgets.QLabel("예측 결과 필터")
        pred_filter_main_layout.addWidget(pred_filters_title)
        
        # Pred filters container
        self.pred_filters_container = QtWidgets.QWidget()
        pred_filter_layout = QtWidgets.QVBoxLayout(self.pred_filters_container)
        
        self.btn_clear_pred_filters = QtWidgets.QPushButton("모든 필터 해제")
        self.btn_clear_pred_filters.clicked.connect(self.clear_pred_filters)
        pred_filter_layout.addWidget(self.btn_clear_pred_filters)
        
        # Container for pred filter checkboxes with scroll
        self.pred_filter_scroll = QtWidgets.QScrollArea()
        self.pred_filter_scroll.setMaximumHeight(200)
        self.pred_filter_widget = QtWidgets.QWidget()
        self.pred_filter_checkboxes_layout = QtWidgets.QGridLayout(self.pred_filter_widget)
        self.pred_filter_scroll.setWidget(self.pred_filter_widget)
        self.pred_filter_scroll.setWidgetResizable(True)
        pred_filter_layout.addWidget(self.pred_filter_scroll)
        
        pred_filter_main_layout.addWidget(self.pred_filters_container)
        
        # Set size constraints for prediction filter section
        grp_pred_filter.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        controls_layout.addWidget(grp_pred_filter)

        # Navigation and settings
        nav_widget = QtWidgets.QWidget()
        nav_layout = QtWidgets.QVBoxLayout(nav_widget)
        
        # Navigation buttons
        nav_buttons = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("이전")
        self.btn_next = QtWidgets.QPushButton("다음")
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)
        nav_buttons.addWidget(self.btn_prev)
        nav_buttons.addWidget(self.btn_next)
        nav_layout.addLayout(nav_buttons)
        
        # Auto-advance setting
        self.chk_auto_advance = QtWidgets.QCheckBox("리뷰 완료 후 자동 다음 이동")
        self.chk_auto_advance.setChecked(self.auto_advance_enabled)
        self.chk_auto_advance.toggled.connect(self.on_auto_advance_toggled)
        nav_layout.addWidget(self.chk_auto_advance)
        
        # Set size constraints for navigation section
        nav_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        
        controls_layout.addWidget(nav_widget)

        # Column 3: Data preview table
        table_panel = QtWidgets.QWidget()
        table_layout = QtWidgets.QVBoxLayout(table_panel)
        table_layout.setContentsMargins(3, 3, 3, 3)
        table_layout.setSpacing(3)
        
        # Data table header
        table_label = QtWidgets.QLabel("데이터 미리보기")
        table_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        table_layout.addWidget(table_label)
        

        
        self.table = QtWidgets.QTableWidget()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)  # Hide row numbers
        self.table.setWordWrap(False)
        
        # Enable column resizing by user
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        
        self.table.cellDoubleClicked.connect(self.on_table_double_click)
        self.table.cellClicked.connect(self.on_table_click)  # Also handle single clicks
        
        # Connect scroll event for auto-loading more data
        self.table.verticalScrollBar().valueChanged.connect(self._on_table_scroll)
        
        # Set table to expand and take remaining space
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.table.setMinimumHeight(400)  # Ensure minimum 50%+ of 900px window
        
        table_layout.addWidget(self.table, 1)  # Stretch factor 1 to take remaining space

        # Add all three columns to splitter
        splitter.addWidget(image_panel)
        splitter.addWidget(controls_panel)
        splitter.addWidget(table_panel)
        splitter.setSizes([600, 400, 400])  # 3-column layout: image, controls, table

        # Connect filter controls
        self.chk_unlabeled.toggled.connect(self.apply_filters)
        self.cmb_label_state.currentTextChanged.connect(self.apply_filters)
        self.cmb_label_value.currentTextChanged.connect(self.apply_filters)
        self.cmb_model_name.currentTextChanged.connect(self.apply_filters)
        self.chk_bookmarks.toggled.connect(self.apply_filters)

    def _create_status_widgets(self) -> None:
        """Create status bar widgets for real-time information display"""
        # Create status widgets
        self.lbl_save_status = QtWidgets.QLabel("저장 상태: 대기")
        self.lbl_save_status.setStyleSheet("color: #666; font-size: 11px; padding: 2px 8px;")
        
        self.lbl_memory_status = QtWidgets.QLabel("메모리: --")
        self.lbl_memory_status.setStyleSheet("color: #666; font-size: 11px; padding: 2px 8px;")
        
        self.lbl_progress_status = QtWidgets.QLabel("진행률: --")
        self.lbl_progress_status.setStyleSheet("color: #666; font-size: 11px; padding: 2px 8px;")
        
        self.lbl_current_position = QtWidgets.QLabel("위치: --")
        self.lbl_current_position.setStyleSheet("color: #666; font-size: 11px; padding: 2px 8px;")
        
        # Add separators
        separator1 = QtWidgets.QLabel("|")
        separator1.setStyleSheet("color: #ccc; font-size: 11px; padding: 2px 4px;")
        separator2 = QtWidgets.QLabel("|")
        separator2.setStyleSheet("color: #ccc; font-size: 11px; padding: 2px 4px;")
        separator3 = QtWidgets.QLabel("|")
        separator3.setStyleSheet("color: #ccc; font-size: 11px; padding: 2px 4px;")
        
        # Add widgets to status bar
        self.status.addPermanentWidget(self.lbl_save_status)
        self.status.addPermanentWidget(separator1)
        self.status.addPermanentWidget(self.lbl_memory_status)
        self.status.addPermanentWidget(separator2)
        self.status.addPermanentWidget(self.lbl_progress_status)
        self.status.addPermanentWidget(separator3)
        self.status.addPermanentWidget(self.lbl_current_position)
        
        # Start timer for periodic updates
        self._status_update_timer = QtCore.QTimer()
        self._status_update_timer.timeout.connect(self._update_status_widgets)
        self._status_update_timer.start(2000)  # Update every 2 seconds

    def _update_status_widgets(self) -> None:
        """Update status bar widgets with real-time information"""
        try:
            # Update memory status
            memory_mb = get_memory_usage()
            self.lbl_memory_status.setText(f"메모리: {memory_mb:.1f}MB")
            
            # Update progress status
            if self.df is not None:
                total_rows = len(self.df)
                labeled_rows = len(self.df[~(self.df[self.active_label_col].isna() | (self.df[self.active_label_col] == ""))])
                progress = (labeled_rows / total_rows * 100) if total_rows > 0 else 0
                self.lbl_progress_status.setText(f"진행률: {labeled_rows:,}/{total_rows:,} ({progress:.1f}%)")
            else:
                self.lbl_progress_status.setText("진행률: --")
            
            # Update current position
            if self.df is not None and self.filtered_indices:
                current_pos = self.current_idx + 1 if self.current_idx < len(self.filtered_indices) else 0
                total_filtered = len(self.filtered_indices)
                self.lbl_current_position.setText(f"위치: {current_pos}/{total_filtered}")
            else:
                self.lbl_current_position.setText("위치: --")
                
        except Exception as e:
            print(f"상태 업데이트 오류: {e}")

    def _update_save_status(self, status: str, color: str = "#666") -> None:
        """Update save status with custom color"""
        self.lbl_save_status.setText(f"저장 상태: {status}")
        self.lbl_save_status.setStyleSheet(f"color: {color}; font-size: 11px; padding: 2px 8px;")

    def _create_toolbar(self) -> None:
        """Create modern toolbar with frequently used actions"""
        toolbar = self.addToolBar("도구")
        toolbar.setMovable(False)

        
        # Navigation actions
        prev_action = toolbar.addAction("⬅️ 이전 (←/A)")
        prev_action.triggered.connect(self.on_prev)
        prev_action.setShortcut("Left")
        
        next_action = toolbar.addAction("➡️ 다음 (→/D/Space)")
        next_action.triggered.connect(self.on_next)
        next_action.setShortcut("Right")
        
        toolbar.addSeparator()
        
        # Labeling actions
        bookmark_action = toolbar.addAction("🔖 북마크 (B)")
        bookmark_action.triggered.connect(self.toggle_bookmark)
        bookmark_action.setShortcut("B")
        
        toolbar.addSeparator()
        
        # View actions
        stats_action = toolbar.addAction("📊 통계")
        stats_action.triggered.connect(self._show_performance_stats)
        
        memory_action = toolbar.addAction("💾 메모리")
        memory_action.triggered.connect(self._show_memory_info)
        
        toolbar.addSeparator()
        
        # Settings
        reload_action = toolbar.addAction("🔄 새로고침")
        reload_action.triggered.connect(self.load_csv_data)

    def _create_progress_dashboard(self) -> QtWidgets.QWidget:
        """Create progress dashboard with statistics"""
        dashboard = QtWidgets.QWidget()

        dashboard.setMaximumHeight(80)
        
        layout = QtWidgets.QVBoxLayout(dashboard)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Title
        title_label = QtWidgets.QLabel("📊 진행 현황")
        title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1976d2;")
        layout.addWidget(title_label)
        
        # Progress bar and stats in horizontal layout
        progress_layout = QtWidgets.QHBoxLayout()
        
        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar, 2)
        
        # Stats label
        self.stats_label = QtWidgets.QLabel("로딩 중...")
        self.stats_label.setStyleSheet("font-size: 12px; color: #424242; min-width: 200px;")
        progress_layout.addWidget(self.stats_label, 1)
        
        layout.addLayout(progress_layout)
        
        return dashboard

    def _create_modern_label_button(self, text: str, shortcut: int) -> QtWidgets.QPushButton:
        """Create a modern styled label button with shortcut hint"""
        # Choose color based on label type
        color_map = {
            'OK': '#4caf50',
            'NG': '#f44336',
            'NG_BUT': '#ff9800',
            '보류': '#9c27b0',
            'SR-이물->OK': '#2196f3',
            'SR-이물->도금-찍힘': '#795548'
        }
        
        color = color_map.get(text, '#757575')  # Default gray
        
        btn = QtWidgets.QPushButton(f"{text} ({shortcut})")
        
        # Add tooltip with shortcut info
        btn.setToolTip(f"단축키: {shortcut}")
        
        return btn



    def _create_quick_filters(self) -> QtWidgets.QWidget:
        """Create quick filter buttons for common operations"""
        widget = QtWidgets.QWidget()
        
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        
        title_label = QtWidgets.QLabel("빠른 필터:")
        layout.addWidget(title_label)
        
        # Quick filter buttons
        quick_filters = [
            ("라벨없음", self._filter_unlabeled, "#ff9800"),
            ("OK만", self._filter_ok_only, "#4caf50"),
            ("NG만", self._filter_ng_only, "#f44336"), 
            ("북마크", self._filter_bookmarks, "#2196f3"),
            ("전체보기", self._show_all, "#2196f3")
        ]
        
        for text, func, color in quick_filters:
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(func)
            layout.addWidget(btn)
        
        layout.addStretch()
        return widget



    def _filter_unlabeled(self) -> None:
        """Quick filter: show only unlabeled items"""
        self.cmb_label_state.setCurrentText("라벨안됨")
        self.chk_bookmarks.setChecked(False)

    def _filter_ok_only(self) -> None:
        """Quick filter: show only OK items"""
        self.cmb_label_state.setCurrentText("라벨됨")
        self.cmb_label_value.setCurrentText("OK")
        self.chk_bookmarks.setChecked(False)

    def _filter_ng_only(self) -> None:
        """Quick filter: show only NG items"""
        self.cmb_label_state.setCurrentText("라벨됨")
        self.cmb_label_value.setCurrentText("NG")
        self.chk_bookmarks.setChecked(False)

    def _filter_bookmarks(self) -> None:
        """Quick filter: show only bookmarked items"""
        self.chk_bookmarks.setChecked(True)

    def _show_all(self) -> None:
        """Quick filter: show all items"""
        self.cmb_label_state.setCurrentText("전체")
        self.cmb_label_value.setCurrentText("전체")
        self.chk_bookmarks.setChecked(False)
        # Clear pred filters
        for checkbox in self.pred_filter_checkboxes.values():
            checkbox.setChecked(False)
        self.selected_pred_filters.clear()

    def _update_progress_dashboard(self) -> None:
        """Update progress dashboard with current statistics"""
        if self.df is None or not hasattr(self, 'progress_bar'):
            return
            
        try:
            total_items = len(self.df)
            if total_items == 0:
                return
                
            # Count labeled items
            labeled_count = 0
            if self.active_label_col in self.df.columns:
                labeled_mask = ~pd.isna(self.df[self.active_label_col]) & (self.df[self.active_label_col] != "")
                labeled_count = labeled_mask.sum()
            
            # Calculate progress percentage
            progress_percent = (labeled_count / total_items) * 100 if total_items > 0 else 0
            
            # Update progress bar
            self.progress_bar.setValue(int(progress_percent))
            
            # Count different label types
            label_stats = {}
            if self.active_label_col in self.df.columns:
                label_counts = self.df[self.active_label_col].value_counts()
                for label, count in label_counts.items():
                    if pd.notna(label) and label != "":
                        label_stats[str(label)] = int(count)
            
            # Create stats text
            remaining = total_items - labeled_count
            filtered_total = len(self.filtered_indices) if self.filtered_indices else 0
            
            stats_text = f"✅ {labeled_count:,} 완료 | ⏳ {remaining:,} 남음 | 🎯 {progress_percent:.1f}%"
            if filtered_total != total_items:
                stats_text += f" | 🔍 필터됨: {filtered_total:,}/{total_items:,}"
            
            self.stats_label.setText(stats_text)
            
            # Update progress bar text
            self.progress_bar.setFormat(f"{progress_percent:.1f}% ({labeled_count:,}/{total_items:,})")
            
        except Exception as e:
            print(f"Progress dashboard update error: {e}")

    def _create_collapsible_section_button(self, title: str, is_expanded: bool = True) -> QtWidgets.QPushButton:
        """Create a styled collapsible section toggle button"""
        arrow = "▼" if is_expanded else "▶"
        btn = QtWidgets.QPushButton(f"{arrow} {title}")
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                font-weight: 700;
                font-size: 14px;
                background: qlineargradient(y1:0, y2:1, stop:0 #4caf50, stop:1 #388e3c);
                border: 2px solid #2e7d32;
                border-radius: 8px;
                padding: 12px 16px;
                margin: 3px 0px;
                color: white;
                min-height: 25px;
            }
            QPushButton:hover {
                background: qlineargradient(y1:0, y2:1, stop:0 #66bb6a, stop:1 #4caf50);
                border-color: #1b5e20;
                font-size: 15px;
            }
            QPushButton:pressed {
                background: qlineargradient(y1:0, y2:1, stop:0 #2e7d32, stop:1 #1b5e20);
                border: 3px solid #1b5e20;
                font-weight: 800;
            }
        """)
        return btn

    def _connect_shortcuts(self) -> None:
        """Connect keyboard shortcuts for labeling"""
        shortcuts = [
            # Labeling shortcuts
            ("1", lambda: self._assign_by_index(0)),
            ("2", lambda: self._assign_by_index(1)),
            ("3", lambda: self._assign_by_index(2)),
            ("4", lambda: self._assign_by_index(3)),
            ("5", lambda: self._assign_by_index(4)),
            ("7", self._toggle_as_is_tobe_mode),
            ("Return", self._apply_all_tobe_selections),  # Enter key for apply all
            
            # Navigation shortcuts - multiple options
            ("Left", self.on_prev),
            ("Right", self.on_next),
            ("Up", self.on_prev),
            ("Down", self.on_next),
            ("a", self.on_prev),
            ("d", self.on_next),
            ("A", self.on_prev),
            ("D", self.on_next),
            ("Space", self.on_next),
            
            # Other shortcuts
            ("b", self.toggle_bookmark),
            ("B", self.toggle_bookmark),
        ]
        
        for key, func in shortcuts:
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            shortcut.activated.connect(func)
            shortcut.setContext(QtCore.Qt.ApplicationShortcut)  # Make shortcuts work globally

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle key press events for navigation and labeling"""
        key = event.key()
        modifiers = event.modifiers()
        
        # Navigation keys
        if key == QtCore.Qt.Key_Left or key == QtCore.Qt.Key_Up:
            self.on_prev()
            event.accept()
            return
        elif key == QtCore.Qt.Key_Right or key == QtCore.Qt.Key_Down:
            self.on_next()
            event.accept()
            return
        elif key == QtCore.Qt.Key_Space:
            self.on_next()
            event.accept()
            return
        
        # Letter keys (case insensitive)
        elif key == QtCore.Qt.Key_A:
            self.on_prev()
            event.accept()
            return
        elif key == QtCore.Qt.Key_D:
            self.on_next()
            event.accept()
            return
        elif key == QtCore.Qt.Key_B:
            self.toggle_bookmark()
            event.accept()
            return
        
        # Number keys for labeling
        elif key == QtCore.Qt.Key_1:
            self._assign_by_index(0)
            event.accept()
            return
        elif key == QtCore.Qt.Key_2:
            self._assign_by_index(1)
            event.accept()
            return
        elif key == QtCore.Qt.Key_3:
            self._assign_by_index(2)
            event.accept()
            return
        elif key == QtCore.Qt.Key_4:
            self._assign_by_index(3)
            event.accept()
            return
        elif key == QtCore.Qt.Key_5:
            self._assign_by_index(4)
            event.accept()
            return
        elif key == QtCore.Qt.Key_7:
            self._toggle_as_is_tobe_mode()
            event.accept()
            return
        elif key == QtCore.Qt.Key_Return or key == QtCore.Qt.Key_Enter:
            self._apply_all_tobe_selections()
            event.accept()
            return
        
        # Call parent class for other keys
        super().keyPressEvent(event)

    def _get_smart_visible_indices(self) -> List[int]:
        """Get smart visible indices ensuring current row is always visible"""
        if not self.filtered_indices:
            return []
        
        # Configuration
        window_size = 100  # Number of rows to show around current position
        buffer_size = 50   # Buffer size for smooth scrolling
        
        # Calculate the range to show
        current_pos = self.current_idx
        total_items = len(self.filtered_indices)
        
        # Calculate start and end positions
        start_pos = max(0, current_pos - buffer_size)
        end_pos = min(total_items, current_pos + buffer_size + 1)
        
        # Adjust if we're near the beginning or end
        if end_pos - start_pos < window_size:
            if start_pos == 0:
                # Near beginning, extend to the right
                end_pos = min(total_items, start_pos + window_size)
            elif end_pos == total_items:
                # Near end, extend to the left
                start_pos = max(0, end_pos - window_size)
        
        # Get the visible indices
        visible_indices = self.filtered_indices[start_pos:end_pos]
        
        # Store the mapping for later use
        self._table_start_pos = start_pos
        self._table_end_pos = end_pos
        
        return visible_indices

    def load_csv_data(self) -> None:
        """Load the CSV data and set up the interface - optimized for large files"""
        if not os.path.exists(self.csv_path):
            QtWidgets.QMessageBox.warning(self, "오류", f"CSV 파일을 찾을 수 없음: {self.csv_path}")
            return
            
        try:
            # Show loading progress for large files
            self.status.showMessage("대용량 CSV 파일 로드 중...")
            QtWidgets.QApplication.processEvents()  # Allow UI to update
            
            # Load CSV with optimized settings for large files
            self.df = pd.read_csv(
                self.csv_path,
                low_memory=False,  # Read entire file at once for consistency
                dtype_backend='numpy_nullable',  # Use nullable dtypes for better memory usage
                engine='c'  # Use C engine for better performance
            )
            
            # Force garbage collection after loading
            force_garbage_collection()
            
            self.status.showMessage(f"{self.csv_path}에서 {len(self.df):,}개 행 로드됨")
            
            # Set up JSON path
            self.json_path = default_json_path(self.csv_path.replace('.csv', '.xlsx'))
            
            # Ensure the review label column exists
            if self.active_label_col not in self.df.columns:
                self.df[self.active_label_col] = ""
                ensure_object_dtype(self.df, self.active_label_col)
            
            # Load existing labels
            merge_json_into_df(self.json_path, self.df, [self.active_label_col])
            
            # Extract TO-BE choices from pred_seg_results
            self.compute_tobe_choices()
            self.compute_pred_filter_choices()
            self.setup_model_name_filter()
            
            # Set up UI with progress updates
            self.status.showMessage("UI 초기화 중...")
            QtWidgets.QApplication.processEvents()
            
            self.refresh_label_controls()
            self.refresh_pred_filter_controls()
            
            # Defer heavy UI updates
            QtCore.QTimer.singleShot(100, self.refresh_as_is_tobe_panel)
            QtCore.QTimer.singleShot(200, self.apply_filters)
            
            self.status.showMessage(f"로드 완료: {len(self.df):,}개 행 준비됨", 2000)
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "오류", f"CSV 로드 실패: {str(e)}")

    def compute_tobe_choices(self) -> None:
        """Extract unique values from pred_seg_results for TO-BE choices"""
        if self.df is None or "pred_seg_results" not in self.df.columns:
            return
        
        choices = set()
        for val in self.df["pred_seg_results"].dropna():
            pred_list = parse_pred_list(val)
            choices.update(pred_list)
        
        # Combine with standard choices
        all_choices = set(self.label_choices + list(choices))
        self.tobe_choices = sorted(all_choices)

    def compute_pred_filter_choices(self) -> None:
        """Extract unique pred_seg_results values for filtering"""
        if self.df is None or "pred_seg_results" not in self.df.columns:
            return
        
        choices = set()
        for val in self.df["pred_seg_results"].dropna():
            pred_list = parse_pred_list(val)
            choices.update(pred_list)
        
        self.pred_filter_choices = sorted(choices)

    def setup_model_name_filter(self) -> None:
        """Set up model_name filter dropdown"""
        self.cmb_model_name.clear()
        self.cmb_model_name.addItem("전체")
        
        if self.df is None or "model_name" not in self.df.columns:
            return
        
        # Get unique model names
        unique_models = sorted(self.df["model_name"].dropna().unique())
        self.cmb_model_name.addItems(unique_models)

    def refresh_pred_filter_controls(self) -> None:
        """Update pred_seg_results filter checkboxes"""
        # Clear existing checkboxes
        for i in reversed(range(self.pred_filter_checkboxes_layout.count())):
            child = self.pred_filter_checkboxes_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        self.pred_filter_checkboxes.clear()
        
        # Create checkboxes for each unique pred value
        for i, choice in enumerate(self.pred_filter_choices):
            checkbox = QtWidgets.QCheckBox(choice)
            checkbox.toggled.connect(self.on_pred_filter_changed)
            self.pred_filter_checkboxes[choice] = checkbox
            
            row, col = divmod(i, 3)  # 3 columns
            self.pred_filter_checkboxes_layout.addWidget(checkbox, row, col)

    def on_pred_filter_changed(self):
        """Handle pred filter checkbox changes"""
        self.selected_pred_filters.clear()
        for choice, checkbox in self.pred_filter_checkboxes.items():
            if checkbox.isChecked():
                self.selected_pred_filters.add(choice)
        self.apply_filters()

    def clear_pred_filters(self):
        """Clear all pred filter selections"""
        for checkbox in self.pred_filter_checkboxes.values():
            checkbox.setChecked(False)
        self.selected_pred_filters.clear()
        self.apply_filters()

    def refresh_label_controls(self) -> None:
        """Update the labeling button controls"""
        # Clear existing buttons
        for i in reversed(range(self.choice_buttons_layout.count())):
            child = self.choice_buttons_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Create buttons for label choices - 3 column layout
        for i, choice in enumerate(self.label_choices):
            btn = self._create_modern_label_button(choice, i+1)
            btn.clicked.connect(lambda _, idx=i: self._assign_by_index(idx))
            row, col = divmod(i, 3)  # Changed to 3 columns
            self.choice_buttons_layout.addWidget(btn, row, col)
        
        # Add AS-IS/TO-BE mode toggle button (7번)
        btn_tobe_mode = self._create_modern_label_button("AS-IS/TO-BE", 7)
        btn_tobe_mode.clicked.connect(self._toggle_as_is_tobe_mode)
        
        # Set button style based on mode
        if self.as_is_tobe_mode:
            btn_tobe_mode.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #45a049;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
        else:
            btn_tobe_mode.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 2px solid #ddd;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
            """)
        
        # Add the button to the layout (next row after existing buttons)
        next_row = (len(self.label_choices) + 2) // 3
        self.choice_buttons_layout.addWidget(btn_tobe_mode, next_row, 0, 1, 3)  # Span all 3 columns
        
        # Adjust container size based on number of buttons (including AS-IS/TO-BE button)
        num_rows = ((len(self.label_choices) + 2) // 3) + 1  # +1 for AS-IS/TO-BE button row
        button_height = 35  # Normal height per button including margins
        container_height = num_rows * button_height + 10
        self.choice_buttons_container.setMinimumHeight(container_height)
        
        # Update label value filter
        self.cmb_label_value.clear()
        self.cmb_label_value.addItem("전체")
        self.cmb_label_value.addItems(self.label_choices)



    def refresh_as_is_tobe_panel(self) -> None:
        """Update the AS-IS → TO-BE mapping panel"""
        # Clear existing widgets
        for i in reversed(range(self.as_is_tobe_layout.count())):
            child = self.as_is_tobe_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        if self.df is None or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        if "pred_seg_results" not in self.df.columns:
            return
            
        pred_val = self.df.at[row_idx, "pred_seg_results"]
        pred_list = parse_pred_list(pred_val)
        
        if not pred_list:
            lbl = QtWidgets.QLabel("AS-IS 매핑용 예측 데이터 없음")
            self.as_is_tobe_layout.addWidget(lbl, 0, 0, 1, 2)
            return
        
        # Create AS-IS → TO-BE mappings
        self.tobe_combos = []  # Store combos for batch apply
        for i, as_is_val in enumerate(pred_list[:5]):  # Limit to 5 items
            lbl_as_is = QtWidgets.QLabel(f"AS-IS: {as_is_val}")
            cmb_tobe = QtWidgets.QComboBox()
            cmb_tobe.addItems(["→"] + self.tobe_choices)
            self.tobe_combos.append(cmb_tobe)
            
            # Try to pre-select best match
            best_match = self._find_best_tobe_match(as_is_val)
            if best_match and best_match in self.tobe_choices:
                cmb_tobe.setCurrentText(best_match)
            
            # Set tab order for keyboard navigation
            if i == 0:
                # First combo gets focus when AS-IS/TO-BE mode is activated
                cmb_tobe.setFocusPolicy(QtCore.Qt.StrongFocus)
            else:
                cmb_tobe.setFocusPolicy(QtCore.Qt.StrongFocus)
            
            self.as_is_tobe_layout.addWidget(lbl_as_is, i, 0)
            self.as_is_tobe_layout.addWidget(cmb_tobe, i, 1)
        
        # Add "Apply All" button (only this button, no individual apply buttons)
        if len(pred_list) > 0:
            btn_apply_all = QtWidgets.QPushButton("모두 적용 (Enter)")
            btn_apply_all.clicked.connect(self._apply_all_tobe_selections)
            btn_apply_all.setFocusPolicy(QtCore.Qt.StrongFocus)
            self.as_is_tobe_layout.addWidget(btn_apply_all, len(pred_list), 0, 1, 2)
            
            # Set tab order: combos -> apply all button
            for i, combo in enumerate(self.tobe_combos):
                if i < len(self.tobe_combos) - 1:
                    QtWidgets.QWidget.setTabOrder(combo, self.tobe_combos[i + 1])
                else:
                    QtWidgets.QWidget.setTabOrder(combo, btn_apply_all)

    def _find_best_tobe_match(self, as_is_val: str) -> Optional[str]:
        """Find the best TO-BE match for an AS-IS value using simple heuristics"""
        as_is_lower = as_is_val.lower()
        
        # Direct match
        if as_is_val in self.tobe_choices:
            return as_is_val
            
        # Partial matching heuristics
        for choice in self.tobe_choices:
            choice_lower = choice.lower()
            if as_is_lower in choice_lower or choice_lower in as_is_lower:
                return choice
        
        return None

    def _apply_tobe_selection(self, combo: QtWidgets.QComboBox) -> None:
        """Apply the selected TO-BE value to the current row"""
        tobe_val = combo.currentText()
        if tobe_val == "→" or not tobe_val:
            return
            
        if self.df is None or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        
        # 기존 라벨을 완전히 덮어쓰기 (추가가 아닌 교체)
        new_label = tobe_val
        
        # 즉시 DataFrame 업데이트
        self.df.at[row_idx, self.active_label_col] = new_label
        
        # 즉시 UI 업데이트
        self._update_current_label_display(row_idx, new_label)
        
        # 배치 저장 (지연 없이)
        self._batch_save_json_entry(row_idx, {"values": {self.active_label_col: new_label}})
        
        # 즉시 테이블 새로고침
        self.refresh_table()
        
        self.status.showMessage(f"TO-BE 라벨 적용됨: {tobe_val}")
        
        # 다음 이미지로 자동 이동
        if self.current_idx < len(self.filtered_indices) - 1:
            self.current_idx += 1
            self.refresh_view()
            self.status.showMessage("다음 이미지로 이동됨", 1000)

    def _apply_all_tobe_selections(self) -> None:
        """Apply all TO-BE selections at once"""
        if self.df is None or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        
        # 모든 선택된 TO-BE 라벨 수집 (기존 라벨 무시하고 새로 생성)
        selected_labels = []
        for combo in self.tobe_combos:
            tobe_val = combo.currentText()
            if tobe_val != "→" and tobe_val:
                selected_labels.append(tobe_val)
        
        # 선택된 라벨들을 세미콜론으로 구분
        new_label = ';'.join(selected_labels) if selected_labels else ""
        
        # 즉시 DataFrame 업데이트
        self.df.at[row_idx, self.active_label_col] = new_label
        
        # 즉시 UI 업데이트
        self._update_current_label_display(row_idx, new_label)
        
        # 배치 저장 (지연 없이)
        self._batch_save_json_entry(row_idx, {"values": {self.active_label_col: new_label}})
        
        # 즉시 테이블 새로고침
        self.refresh_table()
        
        self.status.showMessage(f"모든 TO-BE 라벨 적용됨: {new_label}")
        

        
        # 모두 적용 후 AS-IS/TO-BE 모드 비활성화 및 다음 이미지로 이동
        if self.as_is_tobe_mode:
            self.as_is_tobe_mode = False
            if hasattr(self, 'as_is_tobe_container'):
                self.as_is_tobe_container.setVisible(False)
                self.as_is_tobe_container.setStyleSheet("")
            self.status.showMessage("AS-IS/TO-BE 모드 비활성화됨", 2000)
            # Refresh label controls to update button style
            self.refresh_label_controls()
            
            # 다음 이미지로 자동 이동
            if self.current_idx < len(self.filtered_indices) - 1:
                self.current_idx += 1
                self.refresh_view()
                self.status.showMessage("다음 이미지로 이동됨", 1000)

    def _assign_label_without_advance(self, row_idx: int, label_value: str) -> None:
        """Assign a label to a specific row without auto-advance"""
        if self.df is None:
            return
            
        # Update DataFrame
        self.df.at[row_idx, self.active_label_col] = label_value
        
        # Update performance metrics
        self._label_count += 1
        
        # Save to JSON (batched)
        self._batch_save_json_entry(row_idx, {"values": {self.active_label_col: label_value}})
        

        
        # Immediately update current label display only
        self._update_current_label_display(row_idx, label_value)
        
        # No auto-advance - just update the display
        self._pending_ui_update = True
        self._ui_update_throttle.start()
        
        # 강제로 테이블 새로고침
        QtCore.QTimer.singleShot(100, self.refresh_table)
        


    def _toggle_as_is_tobe_mode(self) -> None:
        """Toggle AS-IS/TO-BE mode for multi-labeling"""
        self.as_is_tobe_mode = not self.as_is_tobe_mode
        
        if self.as_is_tobe_mode:
            self.status.showMessage("AS-IS/TO-BE 모드 활성화 - 다중 라벨링 가능", 2000)
            # Show AS-IS/TO-BE container and highlight it
            if hasattr(self, 'as_is_tobe_container'):
                self.as_is_tobe_container.setVisible(True)
                self.as_is_tobe_container.setStyleSheet("QGroupBox { border: 2px solid #4CAF50; background-color: #E8F5E8; }")
        else:
            self.status.showMessage("AS-IS/TO-BE 모드 비활성화 - 단일 라벨링", 2000)
            # Hide AS-IS/TO-BE container and restore style
            if hasattr(self, 'as_is_tobe_container'):
                self.as_is_tobe_container.setVisible(False)
                self.as_is_tobe_container.setStyleSheet("")
        
        # Refresh label controls to update button style
        self.refresh_label_controls()
        
        # Focus on first TO-BE combo if mode is activated
        if self.as_is_tobe_mode and hasattr(self, 'tobe_combos') and self.tobe_combos:
            QtCore.QTimer.singleShot(100, lambda: self.tobe_combos[0].setFocus())

    def _assign_by_index(self, choice_idx: int) -> None:
        """Assign label by choice index"""
        if choice_idx >= len(self.label_choices):
            return
        if self.df is None or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        choice = self.label_choices[choice_idx]
        
        if self.as_is_tobe_mode:
            # AS-IS/TO-BE 모드: 기존 라벨을 완전히 덮어쓰기
            new_label = choice
            
            # 즉시 DataFrame 업데이트
            self.df.at[row_idx, self.active_label_col] = new_label
            
            # 즉시 UI 업데이트
            self._update_current_label_display(row_idx, new_label)
            
            # 배치 저장 (지연 없이)
            self._batch_save_json_entry(row_idx, {"values": {self.active_label_col: new_label}})
            
            # 즉시 테이블 새로고침
            self.refresh_table()
            
            # 다음 이미지로 자동 이동
            if self.current_idx < len(self.filtered_indices) - 1:
                self.current_idx += 1
                self.refresh_view()
                self.status.showMessage("다음 이미지로 이동됨", 1000)
        else:
            # 일반 모드: 단일 라벨링 (기존 라벨 덮어쓰기) - 자동 진행
            self._assign_label(row_idx, choice)

    def on_auto_advance_toggled(self, checked: bool) -> None:
        """Handle auto-advance setting change"""
        self.auto_advance_enabled = checked


    def _deferred_ui_update(self) -> None:
        """Deferred UI update to improve performance"""
        if self._pending_ui_update:
            self._pending_ui_update = False
            self.refresh_view()
            self._throttled_table_refresh()

    def _throttled_table_refresh(self) -> None:
        """Throttled table refresh for better performance with large datasets"""
        # Only refresh visible portion of table
        if self.df is None or not self.filtered_indices:
            return
        
        # Update only the current row's display instead of full table refresh
        if self.current_idx < len(self.filtered_indices):
            current_row_idx = self.filtered_indices[self.current_idx]
            # Find the table row that corresponds to current_row_idx
            visible_indices = self.filtered_indices[:self.max_table_rows]
            for table_row in range(min(len(visible_indices), self.table.rowCount())):
                if visible_indices[table_row] == current_row_idx:
                    # Update only the label column for this row
                    label_col_idx = None
                    for col_idx in range(self.table.columnCount()):
                        header = self.table.horizontalHeaderItem(col_idx)
                        if header and header.text() == self.active_label_col:
                            label_col_idx = col_idx
                            break
                    
                    if label_col_idx is not None:
                        current_label = self.df.at[current_row_idx, self.active_label_col]
                        item = QtWidgets.QTableWidgetItem(str(current_label) if not pd.isna(current_label) else "")
                        if current_label and str(current_label).strip():
                            item.setBackground(QtGui.QColor(220, 255, 220))  # Green for labeled
                        else:
                            item.setBackground(QtGui.QColor(255, 255, 200))  # Yellow for unlabeled
                        self.table.setItem(table_row, label_col_idx, item)
                    
                    self.table.selectRow(table_row)
                    break

    def _assign_label(self, row_idx: int, label_value: str) -> None:
        """Assign a label to a specific row - optimized for large datasets"""
        if self.df is None:
            return
            
        # Update DataFrame
        self.df.at[row_idx, self.active_label_col] = label_value
        
        # Update performance metrics
        self._label_count += 1
        
        # Save to JSON (batched) - increased batch delay for better performance
        self._batch_save_json_entry(row_idx, {"values": {self.active_label_col: label_value}})
        
        # Immediately update current label display only
        self._update_current_label_display(row_idx, label_value)
        
        # Auto-advance to next item if enabled
        if self.auto_advance_enabled and self.current_idx < len(self.filtered_indices) - 1:
            self.current_idx += 1
            # Minimal view update for auto-advance
            self._minimal_view_update()
            

        else:
            # Deferred UI update for better performance
            self._pending_ui_update = True
            self._ui_update_throttle.start()

    def _update_current_label_display(self, row_idx: int, label_value: str) -> None:
        """Immediately update the current label display without full refresh"""
        if self.df is None or not self.filtered_indices:
            return
        
        # Only update if this is the current row being displayed
        current_row = self.filtered_indices[self.current_idx] if self.current_idx < len(self.filtered_indices) else -1
        if current_row != row_idx:
            return
        
        # Update the current info label
        info_text = f"행 {row_idx + 1}/{len(self.df)} (필터됨: {self.current_idx + 1}/{len(self.filtered_indices)})\n"
        
        # 라벨을 세미콜론으로 구분해서 표시
        if label_value:
            labels = label_value.split(';')
            if len(labels) > 1:
                info_text += f"라벨: {' + '.join(labels)}"
            else:
                info_text += f"라벨: {label_value}"
        else:
            info_text += "라벨: 없음"
        
        # AS-IS/TO-BE 모드 상태 표시
        if self.as_is_tobe_mode:
            info_text += f"\n[AS-IS/TO-BE 모드 활성화 - 다중 라벨링]"
            
        if "pred_seg_results" in self.df.columns:
            pred_val = self.df.at[row_idx, "pred_seg_results"]
            info_text += f"\n예측값: {pred_val}"
        if "model_name" in self.df.columns:
            model_name = self.df.at[row_idx, "model_name"]
            info_text += f"\n모델: {model_name}"
        
        self.lbl_current_info.setText(info_text)
        
        # Update progress dashboard immediately
        self._update_progress_dashboard()
        
        # Defer table update to avoid blocking UI
        QtCore.QTimer.singleShot(200, self._deferred_table_update)
        
        # Save current position immediately
        if hasattr(self, 'settings'):
            self.settings.setValue("current_idx", self.current_idx)

    def _batch_save_json_entry(self, row_idx: int, updater: Dict[str, object]) -> None:
        """Batch save JSON entries and CSV for better performance"""
        self._pending_ops.append((self.json_path, row_idx, updater, {}))
        self._pending_json_path = self.json_path
        self._save_timer.start()
        
        # Update save status
        self._update_save_status("저장 대기 중", "#FFA500")
        
        # Also update DataFrame for real-time CSV saving
        if self.df is not None:
            if "values" in updater:
                for col, value in updater["values"].items():
                    if col in self.df.columns:
                        self.df.at[row_idx, col] = value
            elif "bookmark" in updater:
                # Add bookmark column if it doesn't exist
                if "bookmark" not in self.df.columns:
                    self.df["bookmark"] = False
                self.df.at[row_idx, "bookmark"] = updater["bookmark"]

    def _flush_pending_ops(self) -> None:
        """Flush pending JSON operations - optimized for large datasets"""
        if not self._pending_ops:
            return
        
        try:
            # Load store only once for all operations
            store = load_label_store(self._pending_json_path)
            
            # Batch update all entries
            saved_count = len(self._pending_ops)
            for _json_path, row_idx, updater, _ in self._pending_ops:
                key = str(row_idx)
                entry = store["labels"].get(key) or {}
                for k, v in updater.items():
                    entry[k] = v
                store["labels"][key] = entry
            
            # Save only once after all updates
            save_label_store(self._pending_json_path, store)
            
            # Also save to CSV in real-time
            if saved_count > 0 and self.df is not None:
                try:
                    # Update save status
                    self._update_save_status("저장 중...", "#FFA500")
                    
                    # Create backup before saving (keep only last 5 backups)
                    backup_dir = os.path.dirname(self.csv_path)
                    base_name = os.path.splitext(os.path.basename(self.csv_path))[0]
                    backup_pattern = os.path.join(backup_dir, f"{base_name}_backup_*.csv")
                    
                    # Clean old backups (keep only last 5)
                    import glob
                    backup_files = glob.glob(backup_pattern)
                    backup_files.sort()
                    if len(backup_files) > 5:
                        for old_backup in backup_files[:-5]:
                            try:
                                os.remove(old_backup)
                            except:
                                pass
                    
                    # Create new backup
                    backup_path = self.csv_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
                    if os.path.exists(self.csv_path):
                        import shutil
                        shutil.copy2(self.csv_path, backup_path)
                    
                    # Save to CSV with current labels
                    self.df.to_csv(self.csv_path, index=False)
                    self._update_save_status("저장 완료", "#4CAF50")
                    self.status.showMessage(f"데이터 저장 완료: {saved_count}개 항목 (JSON + CSV)", 1000)
                except Exception as csv_error:
                    print(f"CSV 저장 오류: {csv_error}")
                    self._update_save_status("CSV 저장 실패", "#F44336")
                    self.status.showMessage(f"JSON 저장 완료: {saved_count}개 항목 (CSV 저장 실패)", 1000)
            else:
                self._update_save_status("저장 완료", "#4CAF50")
                self.status.showMessage(f"데이터 저장 완료: {saved_count}개 항목", 1000)
            
            self._pending_ops.clear()
                
        except Exception as e:
            print(f"JSON 저장 오류: {e}")
            self._update_save_status("저장 실패", "#F44336")
            # Don't clear ops if save failed, will retry on next flush

    def _minimal_view_update(self) -> None:
        """Minimal view update for auto-advance - optimized for performance"""
        if self.df is None or not self.filtered_indices or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        
        # Update only essential info
        current_label = self.df.at[row_idx, self.active_label_col] if self.active_label_col in self.df.columns else ""
        info_text = f"행 {row_idx + 1}/{len(self.df)} (필터됨: {self.current_idx + 1}/{len(self.filtered_indices)})\n"
        info_text += f"라벨: {current_label or '(라벨없음)'}"
        if "pred_seg_results" in self.df.columns:
            pred_val = self.df.at[row_idx, "pred_seg_results"]
            info_text += f"\n예측값: {pred_val}"
        if "model_name" in self.df.columns:
            model_name = self.df.at[row_idx, "model_name"]
            info_text += f"\n모델: {model_name}"
        info_text += f"\n\n단축키: 1.OK 2.애매한OK 3.NG 4.애매한NG 5.보류 7.AS-IS/TO-BE모드"
        info_text += f"\n이동: ←→↑↓ 또는 A/D 또는 Space"
        if self.as_is_tobe_mode:
            info_text += f"\nAS-IS/TO-BE: Tab이동 Enter적용"
        self.lbl_current_info.setText(info_text)
        
        # Update bookmark status only
        entry = get_json_entry(self.json_path, row_idx)
        bookmark_status = entry.get("bookmark", False)
        self.lbl_bookmark_status.setText(f"북마크: {'✅' if bookmark_status else '❌'}")
        

        
        # Load image immediately for navigation
        self._load_image_for_row(row_idx)
        
        # Update progress dashboard
        self._update_progress_dashboard()
        
        # Defer AS-IS/TO-BE panel update for better performance
        QtCore.QTimer.singleShot(50, self.refresh_as_is_tobe_panel)

    def _load_image_if_changed(self, row_idx: int) -> None:
        """Load image only if the path has changed - performance optimization"""
        if self.df is None or "img_path" not in self.df.columns:
            return
            
        img_path = self.df.at[row_idx, "img_path"]
        if pd.isna(img_path) or not str(img_path).strip():
            if self._last_image_path != "":
                self.image_label.setText("이미지 경로 없음")
                self.path_label.clear()
                self._last_image_path = ""
            return
        
        resolved_path = resolve_image_path(self.images_base, str(img_path))
        
        # Only load if path changed
        if resolved_path != self._last_image_path:
            self._load_image_for_row(row_idx)
            self._last_image_path = resolved_path

    def _deferred_table_update(self) -> None:
        """Deferred table update with throttling for better performance"""
        current_time = QtCore.QDateTime.currentMSecsSinceEpoch()
        if current_time - self._last_table_update < self._table_update_throttle:
            # Schedule for later
            QtCore.QTimer.singleShot(self._table_update_throttle, self._deferred_table_update)
            return
        
        self._last_table_update = current_time
        self.refresh_table()

    def _update_table_selection(self) -> None:
        """Update table selection to match current image"""
        if self.df is None or not self.filtered_indices or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        
        # Clear current selection first
        self.table.clearSelection()
        
        # Find the table row that corresponds to the current image
        found = False
        for table_row in range(self.table.rowCount()):
            item = self.table.item(table_row, 0)
            if item is not None:
                original_idx = item.data(QtCore.Qt.UserRole)
                if original_idx == row_idx:
                    # Select this row and ensure it's visible
                    self.table.selectRow(table_row)
                    self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                    found = True
                    break
        
        # If not found in current table view, refresh table to show current item
        if not found:
            QtCore.QTimer.singleShot(100, self.refresh_table)

    def _check_and_load_more_data(self, current_table_row: int) -> None:
        """Check if we need to load more data when approaching the end of visible data"""
        if self.df is None or not self.filtered_indices:
            return
        
        # Calculate how many rows are currently visible in the table
        current_visible_count = min(self.max_table_rows, len(self.filtered_indices))
        
        # If we're within 5 rows of the end of visible data, load more
        if current_table_row >= current_visible_count - 5:
            # Check if there are more filtered indices to show
            if len(self.filtered_indices) > current_visible_count:
                # Increase the number of visible rows
                self.max_table_rows = min(self.max_table_rows + 50, len(self.filtered_indices))
                
                # Refresh the table to show more data
                QtCore.QTimer.singleShot(100, self.refresh_table)
                
                # Show status message
                self.status.showMessage(f"더 많은 데이터 로드됨: {self.max_table_rows}개 행 표시", 2000)

    def _check_and_load_more_data_for_navigation(self) -> None:
        """Check if we need to load more data during navigation"""
        if self.df is None or not self.filtered_indices:
            return
        
        # Calculate how many rows are currently visible in the table
        current_visible_count = min(self.max_table_rows, len(self.filtered_indices))
        
        # If we're within 10 rows of the end of visible data, load more
        if self.current_idx >= current_visible_count - 10:
            # Check if there are more filtered indices to show
            if len(self.filtered_indices) > current_visible_count:
                # Increase the number of visible rows
                self.max_table_rows = min(self.max_table_rows + 50, len(self.filtered_indices))
                
                # Refresh the table to show more data
                QtCore.QTimer.singleShot(100, self.refresh_table)
                
                # Show status message
                self.status.showMessage(f"더 많은 데이터 로드됨: {self.max_table_rows}개 행 표시", 2000)

    def _on_table_scroll(self, value: int) -> None:
        """Handle table scroll events for smart loading"""
        if self.df is None or not self.filtered_indices:
            return
        
        # Get scroll bar information
        scroll_bar = self.table.verticalScrollBar()
        max_value = scroll_bar.maximum()
        
        # Calculate which row is currently visible at the top
        if max_value > 0:
            scroll_ratio = value / max_value
            total_visible_rows = self.table.rowCount()
            
            # Estimate which filtered index should be at the top
            if hasattr(self, '_table_start_pos') and total_visible_rows > 0:
                estimated_top_index = int(self._table_start_pos + scroll_ratio * total_visible_rows)
                
                # If we're scrolling to a position that's not in our current window, trigger smart reload
                if (estimated_top_index < self._table_start_pos or 
                    estimated_top_index >= self._table_end_pos):
                    # Defer the reload to avoid too many updates
                    if not hasattr(self, '_scroll_reload_timer'):
                        self._scroll_reload_timer = QtCore.QTimer()
                        self._scroll_reload_timer.setSingleShot(True)
                        self._scroll_reload_timer.timeout.connect(self._trigger_smart_table_reload)
                    
                    self._scroll_reload_timer.start(200)  # 200ms delay

    def _update_image_from_table_selection(self) -> None:
        """Update image based on currently selected table row"""
        if self.df is None or not self.filtered_indices:
            return
        
        # Get the currently selected row in the table
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        
        # Get the first selected row (should be only one)
        selected_row = selected_rows[0].row()
        item = self.table.item(selected_row, 0)
        if item is None:
            return
        
        # Get the original dataframe index from the selected row
        original_idx = item.data(QtCore.Qt.UserRole)
        if original_idx is None:
            return
        
        # Update current_idx to match the selected row
        if original_idx in self.filtered_indices:
            new_current_idx = self.filtered_indices.index(original_idx)
            if new_current_idx != self.current_idx:
                self.current_idx = new_current_idx
        
        # Update the view based on the selected row
        self._minimal_view_update()
        
        # Check if we've reached the end
        if self.current_idx >= len(self.filtered_indices) - 1:
            # If we're at the very last item, show completion message
            self.status.showMessage("모든 항목 라벨링 완료!", 3000)

    def toggle_bookmark(self) -> None:
        """Toggle bookmark for current row"""
        if self.df is None or self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        entry = get_json_entry(self.json_path, row_idx)
        current_bookmark = entry.get("bookmark", False)
        
        self._batch_save_json_entry(row_idx, {"bookmark": not current_bookmark})
        
        # Update UI immediately
        self.lbl_bookmark_status.setText(f"북마크: {'✅' if not current_bookmark else '❌'}")
        self.status.showMessage(f"행 {row_idx + 1} 북마크: {'켜짐' if not current_bookmark else '꺼짐'}")
        
        # Refresh table to show bookmark status
        self.refresh_table()

    def _get_filter_hash(self) -> str:
        """Generate hash of current filter settings for caching"""
        filter_state = (
            self.cmb_label_state.currentText(),
            self.cmb_label_value.currentText(),
            self.cmb_model_name.currentText(),
            self.chk_bookmarks.isChecked(),
            tuple(sorted(self.selected_pred_filters))
        )
        return str(hash(filter_state))

    def apply_filters(self) -> None:
        """Apply various filters to determine which rows to show - optimized for large datasets"""
        if self.df is None:
            return
        
        # Check if filters have changed to avoid unnecessary recalculation
        current_filter_hash = self._get_filter_hash()
        if self._last_filter_hash == current_filter_hash and self._filter_cache is not None:
            self.filtered_indices = self.df[self._filter_cache].index.tolist()
            self._update_filter_results()
            return
            
        # Start with all rows
        mask = pd.Series([True] * len(self.df), index=self.df.index)
        
        # Label state filter
        label_state = self.cmb_label_state.currentText()
        if label_state == "라벨됨":
            mask &= ~(self.df[self.active_label_col].isna() | (self.df[self.active_label_col] == ""))
        elif label_state == "라벨안됨":
            mask &= (self.df[self.active_label_col].isna() | (self.df[self.active_label_col] == ""))
        
        # Label value filter
        label_value = self.cmb_label_value.currentText()
        if label_value and label_value != "전체":
            mask &= (self.df[self.active_label_col] == label_value)
        
        # Model name filter
        model_name = self.cmb_model_name.currentText()
        if model_name and model_name != "전체" and "model_name" in self.df.columns:
            mask &= (self.df["model_name"] == model_name)
        
        # pred_seg_results filter
        if self.selected_pred_filters and "pred_seg_results" in self.df.columns:
            pred_mask = pd.Series([False] * len(self.df), index=self.df.index)
            for idx, row in self.df.iterrows():
                pred_list = parse_pred_list(row["pred_seg_results"])
                if any(pred_val in self.selected_pred_filters for pred_val in pred_list):
                    pred_mask.at[idx] = True
            mask &= pred_mask
        
        # Bookmarks filter
        if self.chk_bookmarks.isChecked():
            store = load_label_store(self.json_path)
            bookmarked_rows = [int(k) for k, v in store.get("labels", {}).items() if v.get("bookmark", False)]
            mask &= self.df.index.isin(bookmarked_rows)
        
        # Cache filter results and update indices
        self._filter_cache = mask
        self._last_filter_hash = current_filter_hash
        self.filtered_indices = self.df[mask].index.tolist()
        
        self._update_filter_results()

    def _update_filter_results(self) -> None:
        """Update UI after filter results are ready"""
        # Ensure current index is valid
        if self.current_idx >= len(self.filtered_indices):
            self.current_idx = max(0, len(self.filtered_indices) - 1)
        
        # Update UI efficiently
        self.refresh_view()
        # Only refresh table if there are filtered results and not too many
        if len(self.filtered_indices) <= self.max_table_rows * 2:
            self.refresh_table()
        else:
            # For very large result sets, defer table refresh
            QtCore.QTimer.singleShot(100, self.refresh_table)
        
        self.status.showMessage(f"전체 {len(self.df)}개 중 {len(self.filtered_indices)}개 행 표시")
        
        # Reset current index to first item when filters change
        self.current_idx = 0  # Reset current index to first item
        
        # Show filter status
        if len(self.filtered_indices) > 0:
            self.status.showMessage(f"필터 적용됨: {len(self.filtered_indices)}개 행", 2000)

    def refresh_view(self) -> None:
        """Refresh the current view (image and info)"""
        if self.df is None or not self.filtered_indices:
            self.lbl_current_info.setText("표시할 데이터 없음")
            self.image_label.clear()
            self.path_label.clear()
            self._update_progress_dashboard()
            return
        
        if self.current_idx >= len(self.filtered_indices):
            return
            
        row_idx = self.filtered_indices[self.current_idx]
        
        # Update current info
        current_label = self.df.at[row_idx, self.active_label_col] if self.active_label_col in self.df.columns else ""
        info_text = f"행 {row_idx + 1}/{len(self.df)} (필터됨: {self.current_idx + 1}/{len(self.filtered_indices)})\n"
        info_text += f"라벨: {current_label or '(라벨없음)'}"
        if "pred_seg_results" in self.df.columns:
            pred_val = self.df.at[row_idx, "pred_seg_results"]
            info_text += f"\n예측값: {pred_val}"
        if "model_name" in self.df.columns:
            model_name = self.df.at[row_idx, "model_name"]
            info_text += f"\n모델: {model_name}"
        info_text += f"\n\n단축키: 1.OK 2.애매한OK 3.NG 4.애매한NG 5.보류 7.AS-IS/TO-BE모드"
        self.lbl_current_info.setText(info_text)
        
        # Update bookmark status
        entry = get_json_entry(self.json_path, row_idx)
        bookmark_status = entry.get("bookmark", False)
        
        self.lbl_bookmark_status.setText(f"북마크: {'✅' if bookmark_status else '❌'}")
        
        # Load and display image (optimized for speed)
        self._load_image_if_changed(row_idx)
        
        # Refresh AS-IS/TO-BE panel
        self.refresh_as_is_tobe_panel()
        
        # Update progress dashboard
        self._update_progress_dashboard()

    def _load_image_for_row(self, row_idx: int) -> None:
        """Load and display image for the given row - optimized for speed"""
        if self.df is None or "img_path" not in self.df.columns:
            return
            
        img_path = self.df.at[row_idx, "img_path"]
        if pd.isna(img_path) or not str(img_path).strip():
            self.image_label.setText("이미지 경로 없음")
            self.path_label.clear()
            return
        
        # Resolve image path
        resolved_path = resolve_image_path(self.images_base, str(img_path))
        
        if not resolved_path or not os.path.exists(resolved_path):
            self.image_label.setText("이미지를 찾을 수 없음")
            self.path_label.setText(f"찾을 수 없음: {img_path}")
            return
        
        # Load image with caching - optimized for speed
        cache_key = resolved_path
        if cache_key in self._image_cache:
            pixmap = self._image_cache[cache_key]
        else:
            # Load image directly without thumbnail building for maximum speed
            pixmap = QtGui.QPixmap(resolved_path)
            
            # Cache management - optimized for speed
            if len(self._image_cache) >= self.image_cache_size * 3:  # Triple cache size for better performance
                # Remove oldest entry
                self._image_cache.pop(next(iter(self._image_cache)))
            self._image_cache[cache_key] = pixmap
        
        if pixmap.isNull():
            self.image_label.setText("이미지 로드 실패")
            self.path_label.setText(f"로드 오류: {resolved_path}")
            return
        
        # Display image - optimized for speed
        if self.fit_to_window:
            scroll_size = self.scroll_area.viewport().size()
            # Use FastTransformation for speed instead of SmoothTransformation
            scaled_pixmap = pixmap.scaled(scroll_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.FastTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setPixmap(pixmap)
        
        self.path_label.setText(resolved_path)

    def refresh_table(self) -> None:
        """Refresh the data table with smart loading - optimized for large datasets"""
        if self.df is None:
            return
        
        # Get visible data (filtered rows only)
        if not self.filtered_indices:
            self.table.setRowCount(0)
            return
        
        # Smart table loading: ensure current row is always visible
        visible_indices = self._get_smart_visible_indices()
        visible_df = self.df.iloc[visible_indices]
        
        # Set up table - add model_name if available
        display_cols = ["img_path", "pred_seg_results", self.active_label_col]
        if "model_name" in visible_df.columns:
            display_cols.insert(-1, "model_name")  # Insert before label column
        display_cols = [col for col in display_cols if col in visible_df.columns]
        
        self.table.setRowCount(len(visible_df))
        self.table.setColumnCount(len(display_cols))
        self.table.setHorizontalHeaderLabels(display_cols)
        
        # Fill table with visible data
        for i, (original_idx, row) in enumerate(visible_df.iterrows()):
            # Check if this row is bookmarked
            entry = get_json_entry(self.json_path, original_idx)
            is_bookmarked = entry.get("bookmark", False)
            
            for j, col in enumerate(display_cols):
                cell_value = str(row[col]) if not pd.isna(row[col]) else ""
                # Truncate long pred_seg_results for better display
                if col == "pred_seg_results" and len(cell_value) > 50:
                    cell_value = cell_value[:47] + "..."
                
                # Add bookmark indicator to first column
                if j == 0 and is_bookmarked:
                    cell_value = "🔖 " + cell_value
                
                item = QtWidgets.QTableWidgetItem(cell_value)
                # Store the original dataframe index in the item for reference
                if j == 0:  # Store in first column
                    item.setData(QtCore.Qt.UserRole, original_idx)
                
                # Color code based on label status
                if col == self.active_label_col:
                    if cell_value and cell_value.strip():
                        # Has label - light green background
                        item.setBackground(QtGui.QColor(220, 255, 220))
                    else:
                        # No label - light yellow background
                        item.setBackground(QtGui.QColor(255, 255, 200))
                elif is_bookmarked:
                    # Bookmark row - light blue background
                    item.setBackground(QtGui.QColor(220, 235, 255))
                
                self.table.setItem(i, j, item)
        
        # Enable column resizing by user
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        
        # Set reasonable initial column widths
        for j, col in enumerate(display_cols):
            if col == "img_path":
                self.table.setColumnWidth(j, 180)
            elif col == "pred_seg_results":
                self.table.setColumnWidth(j, 200)
            elif col == "model_name":
                self.table.setColumnWidth(j, 100)
            elif col == self.active_label_col:
                self.table.setColumnWidth(j, 100)
        
        # Highlight current row in table
        if self.current_idx < len(self.filtered_indices):
            current_row_idx = self.filtered_indices[self.current_idx]
            # Calculate the table row position based on smart loading
            if hasattr(self, '_table_start_pos'):
                table_row = self.current_idx - self._table_start_pos
                if 0 <= table_row < self.table.rowCount():
                    self.table.selectRow(table_row)
                    # Scroll to make sure the selected row is visible
                    item = self.table.item(table_row, 0)
                    if item:
                        self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                else:
                    # Current row is not in the visible range, trigger smart reload
                    self._trigger_smart_table_reload()
            else:
                # Fallback: search for the row
                found = False
                for table_row in range(self.table.rowCount()):
                    item = self.table.item(table_row, 0)
                    if item is not None:
                        original_idx = item.data(QtCore.Qt.UserRole)
                        if original_idx == current_row_idx:
                            self.table.selectRow(table_row)
                            self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                            found = True
                            break
                
                if not found:
                    self._trigger_smart_table_reload()

    def _trigger_smart_table_reload(self) -> None:
        """Trigger smart table reload with loading indicator"""
        # Show loading indicator
        self.status.showMessage("테이블 데이터 로딩 중...", 1000)
        
        # Defer the reload to avoid blocking UI
        QtCore.QTimer.singleShot(50, self._smart_table_reload)

    def _smart_table_reload(self) -> None:
        """Perform smart table reload with current row centering"""
        try:
            # Show loading indicator in table
            self.table.setRowCount(1)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["로딩 중..."])
            
            loading_item = QtWidgets.QTableWidgetItem("🔄 테이블 데이터 로딩 중...")
            loading_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(0, 0, loading_item)
            
            # Defer actual reload
            QtCore.QTimer.singleShot(100, self.refresh_table)
            
        except Exception as e:
            print(f"스마트 테이블 리로드 오류: {e}")
            # Fallback to normal refresh
            self.refresh_table()

    def _check_table_reload_needed(self) -> None:
        """Check if table needs to be reloaded to show current row"""
        if not hasattr(self, '_table_start_pos') or not hasattr(self, '_table_end_pos'):
            # First time, no need to check
            return
        
        # Check if current row is outside the visible range
        if (self.current_idx < self._table_start_pos or 
            self.current_idx >= self._table_end_pos):
            # Current row is not visible, trigger smart reload
            self._trigger_smart_table_reload()

    def on_table_click(self, row: int, _column: int) -> None:
        """Handle single click on table"""
        self._handle_table_selection(row)
    
    def on_table_double_click(self, row: int, _column: int) -> None:
        """Handle double click on table"""
        self._handle_table_selection(row)
    
    def _handle_table_selection(self, row: int) -> None:
        """Handle table row selection (both single and double click)"""
        if row >= self.table.rowCount():
            return
            
        # Get the original dataframe index from the clicked row
        item = self.table.item(row, 0)
        if item is not None:
            original_idx = item.data(QtCore.Qt.UserRole)
            if original_idx is not None and original_idx in self.filtered_indices:
                # Find the position in filtered_indices
                new_current_idx = self.filtered_indices.index(original_idx)
                if new_current_idx != self.current_idx:
                    self.current_idx = new_current_idx
                    # Update image based on the selected row
                    self._update_image_from_table_selection()
                    # Note: Don't call refresh_table() here to avoid recursion
        
        # Check if we need to load more data (if we're near the end of visible data)
        self._check_and_load_more_data(row)

    def on_prev(self) -> None:
        """Navigate to previous item - optimized for speed"""
        print("on_prev called")  # Debug log
        if self.current_idx > 0:
            self.current_idx -= 1
            # Update table selection first, then update view
            self._update_table_selection()
            self._minimal_view_update()
            # Check if table needs smart reload
            self._check_table_reload_needed()
            # Save position change
            self.settings.setValue("current_idx", self.current_idx)
            # Show navigation feedback
            self.status.showMessage(f"이전 항목으로 이동: {self.current_idx + 1}/{len(self.filtered_indices)}", 1000)
        else:
            self.status.showMessage("첫 번째 항목입니다", 1000)

    def on_next(self) -> None:
        """Navigate to next item - optimized for speed"""
        print("on_next called")  # Debug log
        if self.current_idx < len(self.filtered_indices) - 1:
            self.current_idx += 1
            # Update table selection first, then update view
            self._update_table_selection()
            self._minimal_view_update()
            # Check if table needs smart reload
            self._check_table_reload_needed()
            # Save position change
            self.settings.setValue("current_idx", self.current_idx)
            # Show navigation feedback
            self.status.showMessage(f"다음 항목으로 이동: {self.current_idx + 1}/{len(self.filtered_indices)}", 1000)
        else:
            self.status.showMessage("마지막 항목입니다", 1000)

    def on_export_labels(self) -> None:
        """Export labels to Excel"""
        if self.df is None:
            return
            
        output_path = self.csv_path.replace('.csv', '_labeled.xlsx')
        try:
            # Export to Excel
            self.df.to_excel(output_path, index=False, sheet_name="labeled_results")
            QtWidgets.QMessageBox.information(self, "내보내기 완료", f"라벨이 다음 경로로 내보내짐: {output_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "내보내기 오류", f"내보내기 실패: {str(e)}")

    # Memory management methods
    def _clear_image_cache(self) -> None:
        """Clear the image cache"""
        self._image_cache.clear()
        force_garbage_collection()
        self.status.showMessage("이미지 캐시 삭제됨")

    def _show_memory_info(self) -> None:
        """Show memory usage information"""
        memory_mb = get_memory_usage()
        system_mb = get_system_memory()
        cache_size = len(self._image_cache)
        
        msg = f"메모리 사용량: {memory_mb:.1f} MB\n"
        msg += f"시스템 메모리: {system_mb:.1f} MB\n"
        msg += f"이미지 캐시: {cache_size} 개\n"
        msg += f"메모리 제한: {self.max_memory_mb:.1f} MB"
        
        QtWidgets.QMessageBox.information(self, "메모리 정보", msg)

    def _force_memory_cleanup(self) -> None:
        """Force memory cleanup - enhanced for large datasets"""
        self._clear_image_cache()
        self._flush_pending_ops()
        
        # Clear filter cache to save memory
        self._filter_cache = None
        self._last_filter_hash = None
        
        # Force garbage collection multiple times for better cleanup
        for _ in range(3):
            force_garbage_collection()
            QtWidgets.QApplication.processEvents()
        
        memory_after = get_memory_usage()
        self.status.showMessage(f"메모리 정리 완료. 사용량: {memory_after:.1f} MB")

    def _show_performance_stats(self) -> None:
        """Show performance statistics"""
        if self.df is None:
            return
        
        session_duration = datetime.now() - self._session_start_time
        hours = session_duration.total_seconds() / 3600
        
        total_rows = len(self.df)
        labeled_rows = len(self.df[~(self.df[self.active_label_col].isna() | (self.df[self.active_label_col] == ""))])
        progress = (labeled_rows / total_rows * 100) if total_rows > 0 else 0
        
        labels_per_hour = self._label_count / hours if hours > 0 else 0
        
        msg = f"성능 통계:\n"
        msg += f"세션 시간: {session_duration}\n"
        msg += f"이번 세션 라벨링: {self._label_count:,}개\n"
        msg += f"시간당 라벨링 속도: {labels_per_hour:.1f}개/시간\n"
        msg += f"전체 진행률: {labeled_rows:,}/{total_rows:,} ({progress:.1f}%)\n"
        msg += f"남은 예상 시간: {((total_rows - labeled_rows) / labels_per_hour):.1f}시간" if labels_per_hour > 0 else "남은 시간: 계산 불가"
        
        QtWidgets.QMessageBox.information(self, "성능 통계", msg)

    def save_session_state(self) -> None:
        """Save current session state to settings"""
        if self.df is None:
            return
            
        try:
            # Save current position and filter state
            self.settings.setValue("current_idx", self.current_idx)
            self.settings.setValue("auto_advance_enabled", self.auto_advance_enabled)
            
            # Save filter settings
            self.settings.setValue("label_state", self.cmb_label_state.currentText())
            self.settings.setValue("label_value", self.cmb_label_value.currentText())
            self.settings.setValue("model_name", self.cmb_model_name.currentText())
            self.settings.setValue("bookmarks_only", self.chk_bookmarks.isChecked())
            
            # Save pred filter selections
            self.settings.setValue("selected_pred_filters", list(self.selected_pred_filters))
            
            # Save UI section states (collapsed/expanded)
            self.settings.setValue("quick_labeling_expanded", self.quick_labeling_container.isVisible())
            self.settings.setValue("as_is_tobe_expanded", self.as_is_tobe_container.isVisible())
            self.settings.setValue("basic_filters_expanded", self.basic_filters_widget.isVisible())
            self.settings.setValue("pred_filters_expanded", self.pred_filters_container.isVisible())
            # Bookmark memo container no longer exists - skip this setting
            
            # Save window geometry
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("window_state", self.saveState())
            
            print("세션 상태 저장 완료")
            
        except Exception as e:
            print(f"세션 저장 오류: {e}")

    def restore_session_state(self) -> None:
        """Restore session state from settings"""
        if self.df is None:
            return
            
        try:
            # Restore current position
            saved_idx = self.settings.value("current_idx", 0, type=int)
            if 0 <= saved_idx < len(self.filtered_indices):
                self.current_idx = saved_idx
            
            # Restore auto-advance setting
            auto_advance = self.settings.value("auto_advance_enabled", True, type=bool)
            self.auto_advance_enabled = auto_advance
            self.chk_auto_advance.setChecked(auto_advance)
            
            # Restore filter settings
            label_state = self.settings.value("label_state", "전체", type=str)
            if label_state in ["전체", "라벨됨", "라벨안됨"]:
                self.cmb_label_state.setCurrentText(label_state)
            
            label_value = self.settings.value("label_value", "전체", type=str)
            idx = self.cmb_label_value.findText(label_value)
            if idx >= 0:
                self.cmb_label_value.setCurrentIndex(idx)
            
            model_name = self.settings.value("model_name", "전체", type=str)
            idx = self.cmb_model_name.findText(model_name)
            if idx >= 0:
                self.cmb_model_name.setCurrentIndex(idx)
            
            bookmarks_only = self.settings.value("bookmarks_only", False, type=bool)
            self.chk_bookmarks.setChecked(bookmarks_only)
            
            # Restore pred filter selections
            saved_pred_filters = self.settings.value("selected_pred_filters", [], type=list)
            if saved_pred_filters:
                self.selected_pred_filters = set(saved_pred_filters)
                # Update checkboxes
                for choice, checkbox in self.pred_filter_checkboxes.items():
                    checkbox.setChecked(choice in self.selected_pred_filters)
            
            # UI sections are now always visible - no need to restore
            
            # Restore window geometry
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
            window_state = self.settings.value("window_state")
            if window_state:
                self.restoreState(window_state)
            
            # Apply filters and refresh view
            self.apply_filters()
            self.refresh_view()
            
            print(f"세션 상태 복원 완료 - 위치: {self.current_idx}")
            
        except Exception as e:
            print(f"세션 복원 오류: {e}")


    def closeEvent(self, event) -> None:
        """Handle application close event"""
        try:
            # Save session state before closing
            self.save_session_state()
            
            # Flush any pending JSON operations
            self._flush_pending_ops()
            
            event.accept()
            
        except Exception as e:
            print(f"종료 시 저장 오류: {e}")
            event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Check if paths exist
    if not os.path.exists(INFERENCE_CSV_PATH):
        QtWidgets.QMessageBox.critical(None, "오류", f"CSV 파일을 찾을 수 없음: {INFERENCE_CSV_PATH}")
        return
    
    if not os.path.exists(IMAGES_BASE_PATH):
        QtWidgets.QMessageBox.warning(None, "경고", f"이미지 디렉토리를 찾을 수 없음: {IMAGES_BASE_PATH}")
    
    window = InferenceLabelerWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()