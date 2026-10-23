@echo off
rem Creates the launcher's private Python environment (launcher\.venv) and installs its
rem packages. Used by Launcher.bat; does nothing once everything is installed.
cd /d "%~dp0"
if exist .venv\Scripts\python.exe if exist .venv\installed.txt (
  fc /b requirements.txt .venv\installed.txt >nul 2>&1 && exit /b 0
)
if not exist .venv\Scripts\python.exe (
  echo Creating the launcher's Python environment - first run only...
  py -3 -m venv .venv 2>nul
  if not exist .venv\Scripts\python.exe python -m venv .venv 2>nul
)
if not exist .venv\Scripts\python.exe (
  echo.
  echo Python 3.9 or newer was not found.
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add python.exe to PATH" in the installer, then run this again.
  exit /b 1
)
echo Installing the launcher's packages...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installing the packages failed - see the messages above.
  exit /b 1
)
copy /y requirements.txt .venv\installed.txt >nul
exit /b 0
