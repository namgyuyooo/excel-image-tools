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
