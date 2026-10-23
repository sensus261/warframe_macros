@echo off
rem Builds dist\BuffWatch\BuffWatch.exe. Needs Python only on the machine that builds it.
cd /d "%~dp0"
call _setup.bat
if errorlevel 1 goto fail
echo Installing PyInstaller...
.venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --hidden-import PIL._tkinter_finder --name BuffWatch buffwatch.pyw
if errorlevel 1 goto fail
if not exist dist\BuffWatch\BuffWatch.exe goto fail
echo.
echo Done: %~dp0dist\BuffWatch\BuffWatch.exe
echo Keep the whole dist\BuffWatch folder together - the exe needs the files next to it.
pause
exit /b 0

:fail
echo.
echo Build FAILED - see the messages above.
pause
exit /b 1
