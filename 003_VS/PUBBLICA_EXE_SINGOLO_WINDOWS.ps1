\
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$project = Join-Path $root "MeshCoreTracker\MeshCoreTracker.csproj"
$tfm = "net10.0-windows10.0.19041.0"
$rid = "win-x64"
$publishDir = Join-Path $root "publish\win-x64-single"
$distDir = Join-Path $root "DIST_EXE"

Write-Host "" 
Write-Host "MeshCore Tracker - pubblicazione EXE singolo Windows x64" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw "dotnet non trovato. Aprire il Developer PowerShell di Visual Studio o installare .NET 10 SDK/MAUI."
}

if (Test-Path $publishDir) { Remove-Item $publishDir -Recurse -Force }
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
New-Item -ItemType Directory -Path $publishDir -Force | Out-Null
New-Item -ItemType Directory -Path $distDir -Force | Out-Null

Write-Host "Ripristino pacchetti..." -ForegroundColor Yellow
dotnet restore $project -p:TargetFramework=$tfm -p:RuntimeIdentifierOverride=$rid
if ($LASTEXITCODE -ne 0) { throw "dotnet restore fallito." }

Write-Host "Pubblicazione self-contained, unpackaged, single-file..." -ForegroundColor Yellow
dotnet publish $project `
    -f $tfm `
    -c Release `
    -p:RuntimeIdentifierOverride=$rid `
    -p:WindowsPackageType=None `
    -p:WindowsAppSDKSelfContained=true `
    -p:SelfContained=true `
    -p:EnableMsixTooling=true `
    -p:IncludeAllContentForSelfExtract=true `
    -p:PublishSingleFile=true `
    -p:PublishTrimmed=false `
    -p:DebugType=None `
    -p:DebugSymbols=false `
    --no-restore `
    --output $publishDir

if ($LASTEXITCODE -ne 0) { throw "dotnet publish fallito." }

$exe = Get-ChildItem $publishDir -Filter "MeshCoreTracker.exe" -File | Select-Object -First 1
if (-not $exe) {
    throw "MeshCoreTracker.exe non trovato nella cartella di pubblicazione: $publishDir"
}

$finalExe = Join-Path $distDir "MeshCoreTracker.exe"
Copy-Item $exe.FullName $finalExe -Force

$sizeMB = [Math]::Round((Get-Item $finalExe).Length / 1MB, 1)
Write-Host ""
Write-Host "OK - EXE creato:" -ForegroundColor Green
Write-Host "  $finalExe" -ForegroundColor Green
Write-Host "  Dimensione: $sizeMB MB" -ForegroundColor Green
Write-Host ""
Write-Host "Per la distribuzione copia solamente MeshCoreTracker.exe dalla cartella DIST_EXE." -ForegroundColor Cyan
Write-Host "Nota: WebView2 deve essere presente sul PC di destinazione." -ForegroundColor DarkYellow
Write-Host ""
