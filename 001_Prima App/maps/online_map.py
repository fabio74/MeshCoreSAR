from __future__ import annotations

import json

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


HTML = r"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html, body, #map { height: 100%; width: 100%; margin: 0; }
body { background: #e9ecef; }
.leaflet-tooltip { font-family: sans-serif; }
</style>
</head>
<body>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map('map', {zoomControl: true}).setView([45.5, 11.5], 9);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const tracks = {};
const palette = ['#d32f2f','#1976d2','#388e3c','#7b1fa2','#f57c00','#00796b','#455a64','#c2185b'];

function colorFor(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = ((h << 5) - h) + name.charCodeAt(i);
    return palette[Math.abs(h) % palette.length];
}

function upsertTrack(name, points) {
    if (!points || points.length === 0) return;
    const color = colorFor(name);
    const latlngs = points.map(p => [p.lat, p.lon]);

    if (!tracks[name]) {
        const line = L.polyline(latlngs, {color: color, weight: 4, opacity: 0.8}).addTo(map);
        const last = points[points.length - 1];
        const marker = L.circleMarker([last.lat, last.lon], {
            radius: 7, color: color, fillColor: color, fillOpacity: 0.95
        }).addTo(map);
        marker.bindTooltip(name, {permanent: false});
        tracks[name] = {line, marker};
    } else {
        tracks[name].line.setLatLngs(latlngs);
        const last = points[points.length - 1];
        tracks[name].marker.setLatLng([last.lat, last.lon]);
    }

    const last = points[points.length - 1];
    tracks[name].marker.bindPopup(
        '<b>' + name + '</b><br>' +
        last.lat.toFixed(6) + ', ' + last.lon.toFixed(6) +
        (last.alt === null ? '' : '<br>Alt: ' + last.alt.toFixed(1) + ' m') +
        '<br>' + last.time
    );
}

function fitAll() {
    const pts = [];
    Object.values(tracks).forEach(t => {
        t.line.getLatLngs().forEach(p => pts.push(p));
    });
    if (pts.length === 1) map.setView(pts[0], 15);
    else if (pts.length > 1) map.fitBounds(L.latLngBounds(pts), {padding:[40,40]});
}

function clearTracks() {
    Object.values(tracks).forEach(t => {
        map.removeLayer(t.line);
        map.removeLayer(t.marker);
    });
    Object.keys(tracks).forEach(k => delete tracks[k]);
}
</script>
</body>
</html>
"""


class OnlineMapWidget(QWebEngineView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loaded = False
        self._tracks: dict[str, list[dict]] = {}
        self.loadFinished.connect(self._on_loaded)
        self.setHtml(HTML, QUrl("https://local.meshcore-tracker/"))

    def _on_loaded(self, ok: bool) -> None:
        self._loaded = ok
        if ok:
            self.render_all()

    def set_track(self, name: str, points: list[dict]) -> None:
        self._tracks[name] = points
        if self._loaded:
            self.page().runJavaScript(
                f"upsertTrack({json.dumps(name)}, {json.dumps(points)});"
            )

    def render_all(self) -> None:
        if not self._loaded:
            return
        self.page().runJavaScript("clearTracks();")
        for name, points in self._tracks.items():
            self.page().runJavaScript(
                f"upsertTrack({json.dumps(name)}, {json.dumps(points)});"
            )
        self.page().runJavaScript("fitAll();")

    def fit_all(self) -> None:
        if self._loaded:
            self.page().runJavaScript("fitAll();")
