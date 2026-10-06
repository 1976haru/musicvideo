@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment...
  py -3.11 -m venv .venv
)
echo [2/3] Installing or updating MV Director Studio...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[ui,music]"
echo [3/3] Starting MV Director Studio...
".venv\Scripts\python.exe" -m mvstudio.ui_app
if errorlevel 1 pause
endlocal
