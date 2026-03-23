@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo MYRA virtual environment not found.
  pause
  exit /b 1
)

"venv\Scripts\python.exe" "main.py"
