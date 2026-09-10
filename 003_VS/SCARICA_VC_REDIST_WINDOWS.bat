@echo off
setlocal
cd /d "%~dp0"

set "PRE=%~dp0Prerequisiti"
set "OUT=%PRE%\VC_redist.x64.exe"
set "URL=https://aka.ms/vc14/vc_redist.x64.exe"

if not exist "%PRE%" mkdir "%PRE%"

echo Download Microsoft Visual C++ Redistributable x64...
echo.

where curl.exe >nul 2>&1
if errorlevel 1 (
    echo ERRORE: curl.exe non e' disponibile su questo Windows.
    echo.
    echo In alternativa esegui:
    echo powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SCARICA_VC_REDIST_WINDOWS.ps1"
    pause
    exit /b 1
)

curl.exe -L --fail --retry 3 --output "%OUT%" "%URL%"
if errorlevel 1 (
    echo.
    echo ERRORE durante il download.
    pause
    exit /b 1
)

if not exist "%OUT%" (
    echo ERRORE: il file non e' stato creato.
    pause
    exit /b 1
)

echo.
echo OK:
echo %OUT%
echo.
echo Ora puoi eseguire CREA_SETUP_EXE_WINDOWS.bat
pause
