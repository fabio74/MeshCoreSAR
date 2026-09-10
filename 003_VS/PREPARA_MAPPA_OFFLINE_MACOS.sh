#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
RAW="$ROOT/MeshCoreTracker/Resources/Raw"
mkdir -p "$RAW"

echo "Download Leaflet 1.9.4..."
curl -L "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" -o "$RAW/leaflet.js"
curl -L "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" -o "$RAW/leaflet.css"

echo "Download Proj4js 2.22.0..."
curl -L "https://cdn.jsdelivr.net/npm/proj4@2.22.0/dist/proj4.js" -o "$RAW/proj4.js"

echo "Download geotiff.js 3.0.5..."
curl -L "https://cdn.jsdelivr.net/npm/geotiff@3.0.5" -o "$RAW/geotiff.js"

cp "$RAW/map.offline.html" "$RAW/map.html"
echo "OK: asset cartografici locali installati. Ricompilare l'app."
