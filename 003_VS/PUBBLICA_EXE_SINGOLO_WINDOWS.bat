\
@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBBLICA_EXE_SINGOLO_WINDOWS.ps1"
if errorlevel 1 (
  echo.
  echo ERRORE DURANTE LA PUBBLICAZIONE.
  pause
  exit /b 1
)
echo.
echo Pubblicazione completata.
pause
