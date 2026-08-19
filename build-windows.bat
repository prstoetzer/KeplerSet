@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher ^("py"^) was not found. Install Python 3.11 or newer from python.org.
  exit /b 1
)

if not exist .venv (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -e . -r requirements-build.txt
if errorlevel 1 exit /b 1
python scripts\build.py
if errorlevel 1 exit /b 1

echo.
echo Built:
echo   dist\KeplerSet.exe
echo   dist\KeplerSetCLI.exe
endlocal
