@echo off
rem First run creates a private Python environment and installs the dependencies.
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Setting up BuffWatch - first run only...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 ( echo Python 3.9+ is required: https://www.python.org/downloads/ & pause & exit /b 1 )
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 ( pause & exit /b 1 )
)
start "" .venv\Scripts\pythonw.exe buffwatch.pyw %*
