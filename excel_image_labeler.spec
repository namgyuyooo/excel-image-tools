# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['inference_labeler.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'pandas',
        'numpy',
        'PIL',
        'PIL.Image',
        'openpyxl',
        'psutil',
        'create_excel_from_seg_csv',
        'setup_dialog',
        'utils',
        'memory_monitor',
        'shiboken6',
        'dateutil',
        'pytz',
        'tzdata'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='excel_image_labeler.exe',
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
    icon=None,
)
