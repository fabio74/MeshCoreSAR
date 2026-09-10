
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$pre = Join-Path $root "Prerequisiti"
New-Item -ItemType Directory -Path $pre -Force | Out-Null
$out = Join-Path $pre "VC_redist.x64.exe"
$url = "https://aka.ms/vc14/vc_redist.x64.exe"
Write-Host "Download Visual C++ Redistributable x64 da Microsoft..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
Write-Host "OK: $out" -ForegroundColor Green
Write-Host "Per un test immediato puoi eseguirlo manualmente e poi riprovare MeshCoreTracker.exe." -ForegroundColor Yellow
