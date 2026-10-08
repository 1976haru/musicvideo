# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

def _collect_optional_submodules(name):
    try:
        return collect_submodules(name)
    except Exception:
        return []

hidden = collect_submodules("mvstudio") + ["cv2", "librosa", "soundfile", "numpy", "scipy"]
hidden += _collect_optional_submodules("scenedetect")
# SciPy's Array API compatibility layer is imported dynamically by recent SciPy/librosa
# builds. PyInstaller can miss these vendored namespaces, so collect both layouts used
# across supported SciPy versions plus the standalone compatibility package.
for _pkg in (
    "scipy._external.array_api_compat",
    "scipy._lib.array_api_compat",
    "array_api_compat",
):
    hidden += _collect_optional_submodules(_pkg)
hidden = list(dict.fromkeys(hidden))

a = Analysis(
    ["mvstudio_app.py"], pathex=["src"], binaries=[], datas=[], hiddenimports=hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[
        "torch", "open_clip", "beat_this", "allin1", "pytest", "pandas", "pyarrow",
        "matplotlib", "sklearn", "sqlalchemy", "openpyxl", "lxml",
    ], noarchive=False,
    # librosa uses Numba cache=True decorators. Keep its Python sources on disk
    # so Numba has a real source locator in the ONEDIR package.
    module_collection_mode={"librosa": "py"},
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="MV Director Studio",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    version="windows_version_info.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MV_Director_Studio")
