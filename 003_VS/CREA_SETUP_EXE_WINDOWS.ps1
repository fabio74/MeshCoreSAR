
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# 1) publish app folder
& (Join-Path $root "PUBBLICA_CARTELLA_WINDOWS.ps1")

# 2) verify VC redist exists
$vc = Join-Path $root "Prerequisiti\VC_redist.x64.exe"
if (-not (Test-Path $vc)) {
    throw "Manca $vc. Eseguire prima SCARICA_VC_REDIST_WINDOWS.ps1 mentre il PC e' online."
}

# 3) find Inno Setup compiler
$candidates = @(
  "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "Inno Setup 6 non trovato. Installarlo sul PC di sviluppo e rieseguire questo script."
}

$iss = Join-Path $root "MeshCoreTracker_Setup.iss"
& $iscc $iss
if ($LASTEXITCODE -ne 0) { throw "Compilazione installer fallita." }

$setup = Join-Path $root "DIST_SETUP\MeshCoreTracker_Setup.exe"
if (-not (Test-Path $setup)) { throw "Installer non trovato: $setup" }
Write-Host "" 
Write-Host "OK - unico file da distribuire:" -ForegroundColor Green
Write-Host "  $setup" -ForegroundColor Green
