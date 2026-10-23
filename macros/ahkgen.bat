@echo off
rem Drag a .json config onto this file (or run: ahkgen.bat config.json)
if "%~1"=="" (
  echo Usage: drag a JSON config onto ahkgen.bat, or run: ahkgen.bat config.json
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ahkgen.ps1" %*
pause
