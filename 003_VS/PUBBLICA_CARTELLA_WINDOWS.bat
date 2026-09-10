
@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBBLICA_CARTELLA_WINDOWS.ps1"
if errorlevel 1 pause & exit /b 1
pause
