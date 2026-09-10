$ErrorActionPreference = "Stop"
$raw = Join-Path $PSScriptRoot "MeshCoreTracker\Resources\Raw"
New-Item -ItemType Directory -Force -Path $raw | Out-Null

Write-Host "Download Leaflet 1.9.4..."
Invoke-WebRequest "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" -OutFile (Join-Path $raw "leaflet.js")
Invoke-WebRequest "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" -OutFile (Join-Path $raw "leaflet.css")

Write-Host "Download Proj4js 2.22.0..."
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/proj4@2.22.0/dist/proj4.js" -OutFile (Join-Path $raw "proj4.js")

Write-Host "Download geotiff.js 3.0.5 browser bundle..."
Invoke-WebRequest "https://cdn.jsdelivr.net/npm/geotiff@3.0.5" -OutFile (Join-Path $raw "geotiff.js")

Copy-Item (Join-Path $raw "map.offline.html") (Join-Path $raw "map.html") -Force
Write-Host "OK: asset cartografici locali installati. Ricompilare l'app." -ForegroundColor Green
