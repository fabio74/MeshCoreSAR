
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$project = Join-Path $root "MeshCoreTracker\MeshCoreTracker.csproj"
$tfm = "net10.0-windows10.0.19041.0"
$rid = "win-x64"
$distDir = Join-Path $root "DIST_APP"

Write-Host "MeshCore Tracker 1.6 - publish Windows x64 a cartella" -ForegroundColor Cyan
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw "dotnet non trovato." }
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
New-Item -ItemType Directory -Path $distDir -Force | Out-Null

dotnet restore $project -p:TargetFramework=$tfm -p:RuntimeIdentifierOverride=$rid
if ($LASTEXITCODE -ne 0) { throw "dotnet restore fallito." }

dotnet publish $project `
  -f $tfm `
  -c Release `
  -p:RuntimeIdentifierOverride=$rid `
  -p:WindowsPackageType=None `
  -p:WindowsAppSDKSelfContained=true `
  -p:SelfContained=true `
  -p:PublishSingleFile=false `
  -p:PublishTrimmed=false `
  -p:DebugType=None `
  -p:DebugSymbols=false `
  --no-restore `
  --output $distDir
if ($LASTEXITCODE -ne 0) { throw "dotnet publish fallito." }

Write-Host "" 
Write-Host "OK: pubblicazione creata in $distDir" -ForegroundColor Green
Write-Host "Prima di creare l'installer, prova direttamente:" -ForegroundColor Yellow
Write-Host "  $distDir\MeshCoreTracker.exe" -ForegroundColor Yellow
