# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("mvstudio") + ["cv2", "librosa", "soundfile", "numpy"]

a = Analysis(
    ["mvstudio_app.py"], pathex=["src"], binaries=[], datas=[], hiddenimports=hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[
        "torch", "open_clip", "beat_this", "allin1", "pytest", "pandas", "pyarrow",
        "matplotlib", "sklearn", "sqlalchemy", "openpyxl", "lxml",
    ], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="MV Director Studio",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    version="windows_version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MV_Director_Studio")
