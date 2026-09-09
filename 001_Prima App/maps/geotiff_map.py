from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

try:
    import rasterio
    from affine import Affine
    from pyproj import Transformer
    from rasterio.enums import Resampling
except Exception:
    rasterio = None
    Affine = None
    Transformer = None
    Resampling = None


class GeoTiffMapWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.info = QLabel("Carica un GeoTIFF georeferenziato.")
        self.info.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.info)

        self._pixmap: QPixmap | None = None
        self._transform = None
        self._transformer = None
        self._tracks: dict[str, list[dict]] = {}

    @property
    def available(self) -> bool:
        return rasterio is not None

    def load_geotiff(self, path: str | Path) -> tuple[bool, str]:
        if rasterio is None:
            return False, "Supporto GeoTIFF non disponibile: installare rasterio e pyproj."

        path = str(path)
        try:
            with rasterio.open(path) as ds:
                if ds.crs is None:
                    return False, "Il TIFF non contiene un CRS/georeferenziazione."

                scale = min(1.0, 3200.0 / max(ds.width, ds.height))
                out_w = max(1, int(ds.width * scale))
                out_h = max(1, int(ds.height * scale))

                count = min(ds.count, 3)
                data = ds.read(
                    indexes=list(range(1, count + 1)),
                    out_shape=(count, out_h, out_w),
                    resampling=Resampling.bilinear,
                )

                self._transform = ds.transform * Affine.scale(
                    ds.width / out_w,
                    ds.height / out_h,
                )
                self._transformer = Transformer.from_crs(
                    "EPSG:4326", ds.crs, always_xy=True
                )

            if data.shape[0] == 1:
                band = self._to_uint8(data[0])
                rgb = np.dstack([band, band, band])
            else:
                rgb = np.dstack([self._to_uint8(data[i]) for i in range(3)])

            rgb = np.ascontiguousarray(rgb)
            h, w, _ = rgb.shape
            image = QImage(
                rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888
            ).copy()

            self._pixmap = QPixmap.fromImage(image)
            self.info.setText(f"GeoTIFF: {Path(path).name}")
            self._redraw()
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            return True, "GeoTIFF caricato."

        except Exception as exc:
            return False, f"Errore caricamento GeoTIFF: {exc}"

    @staticmethod
    def _to_uint8(a: np.ndarray) -> np.ndarray:
        finite = np.isfinite(a)
        if not finite.any():
            return np.zeros(a.shape, dtype=np.uint8)
        lo = np.nanpercentile(a[finite], 2)
        hi = np.nanpercentile(a[finite], 98)
        if hi <= lo:
            hi = lo + 1
        scaled = np.clip((a.astype(np.float64) - lo) * 255.0 / (hi - lo), 0, 255)
        scaled[~finite] = 0
        return scaled.astype(np.uint8)

    def set_track(self, name: str, points: list[dict]) -> None:
        self._tracks[name] = points
        if self._pixmap is not None:
            self._redraw()

    def _gps_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        if self._transformer is None or self._transform is None:
            raise RuntimeError("GeoTIFF non inizializzato.")
        x, y = self._transformer.transform(lon, lat)
        col, row = (~self._transform) * (x, y)
        return float(col), float(row)

    def _redraw(self) -> None:
        self.scene.clear()
        if self._pixmap is None:
            return

        self.scene.addItem(QGraphicsPixmapItem(self._pixmap))
        palette = [
            QColor("#d32f2f"), QColor("#1976d2"), QColor("#388e3c"),
            QColor("#7b1fa2"), QColor("#f57c00"), QColor("#00796b"),
            QColor("#455a64"), QColor("#c2185b"),
        ]

        for idx, (name, points) in enumerate(self._tracks.items()):
            color = palette[idx % len(palette)]
            pen = QPen(color, 3)
            brush = QBrush(color)
            pixels: list[tuple[float, float]] = []

            for p in points:
                try:
                    pixels.append(self._gps_to_pixel(p["lon"], p["lat"]))
                except Exception:
                    continue

            for a, b in zip(pixels, pixels[1:]):
                line = QGraphicsLineItem(a[0], a[1], b[0], b[1])
                line.setPen(pen)
                self.scene.addItem(line)

            if pixels:
                x, y = pixels[-1]
                marker = QGraphicsEllipseItem(x - 5, y - 5, 10, 10)
                marker.setPen(pen)
                marker.setBrush(brush)
                marker.setToolTip(name)
                self.scene.addItem(marker)
