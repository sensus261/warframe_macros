@echo off
rem Builds dist\BuffWatch\BuffWatch.exe (run run.bat once first to create .venv).
cd /d "%~dp0"
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --name BuffWatch buffwatch.pyw
echo Done: dist\BuffWatch\BuffWatch.exe
pause
