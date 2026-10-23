@echo off
rem Opens the Warframe Toolkit launcher. The first run sets up its Python environment.
cd /d "%~dp0launcher"
call _setup.bat
if errorlevel 1 (
  pause
  exit /b 1
)
start "" .venv\Scripts\pythonw.exe launcher.pyw %*
