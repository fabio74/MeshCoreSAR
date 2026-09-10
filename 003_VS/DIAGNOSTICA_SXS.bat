
@echo off
setlocal
cd /d "%~dp0"
set EXE=%~1
if "%EXE%"=="" set EXE=%~dp0DIST_EXE\MeshCoreTracker.exe
if not exist "%EXE%" (
  echo EXE non trovato: %EXE%
  echo Trascina MeshCoreTracker.exe sopra questo file BAT oppure passalo come parametro.
  pause
  exit /b 1
)

echo Avvio tracciamento SideBySide...
sxstrace.exe Trace -logfile:"%TEMP%\MeshCoreTracker_SxS.etl"
echo.
echo ADESSO avvia manualmente questo EXE e attendi l'errore:
echo "%EXE%"
echo.
pause
sxstrace.exe StopTrace
sxstrace.exe Parse -logfile:"%TEMP%\MeshCoreTracker_SxS.etl" -outfile:"%~dp0MeshCoreTracker_SxS.txt"
echo.
echo Creato: %~dp0MeshCoreTracker_SxS.txt
notepad "%~dp0MeshCoreTracker_SxS.txt"
pause
