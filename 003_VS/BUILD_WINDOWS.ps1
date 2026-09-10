$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "MeshCoreTracker\MeshCoreTracker.csproj"
Write-Host "Ripristino workload/progetto Windows..." -ForegroundColor Cyan
dotnet restore $project -p:TargetFramework=net10.0-windows10.0.19041.0
Write-Host "Compilazione Windows..." -ForegroundColor Cyan
dotnet build $project -c Debug -f net10.0-windows10.0.19041.0 --no-restore
