
@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CREA_SETUP_EXE_WINDOWS.ps1"
if errorlevel 1 (
  echo.
  echo ERRORE.
  pause
  exit /b 1
)
echo.
echo Installer creato.
pause
