from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
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


class ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with mouse-wheel zoom and hand panning."""

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._zoom_factor = 1.20

    def wheelEvent(self, event) -> None:
        factor = self._zoom_factor if event.angleDelta().y() > 0 else 1.0 / self._zoom_factor
        self.scale(factor, factor)
        event.accept()

    def zoom_in(self) -> None:
        self.scale(self._zoom_factor, self._zoom_factor)

    def zoom_out(self) -> None:
        self.scale(1.0 / self._zoom_factor, 1.0 / self._zoom_factor)


class GeoTiffMapWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = ZoomableGraphicsView(self.scene)
        self.info = QLabel("Carica un GeoTIFF georeferenziato. Rotella mouse = zoom, trascinamento = pan.")
        self.info.setWordWrap(True)

        controls = QHBoxLayout()
        zoom_in_button = QPushButton("+")
        zoom_out_button = QPushButton("−")
        fit_button = QPushButton("Adatta")
        zoom_in_button.setToolTip("Zoom avanti")
        zoom_out_button.setToolTip("Zoom indietro")
        fit_button.setToolTip("Adatta l'intera mappa alla finestra")
        zoom_in_button.clicked.connect(self.view.zoom_in)
        zoom_out_button.clicked.connect(self.view.zoom_out)
        fit_button.clicked.connect(self.fit_map)
        controls.addWidget(zoom_in_button)
        controls.addWidget(zoom_out_button)
        controls.addWidget(fit_button)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.info)

        self._pixmap: QPixmap | None = None
        self._transform = None
        self._transformer = None
        self._tracks: dict[str, list[dict]] = {}
        self._visible: dict[str, bool] = {}

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

                # Keep RAM usage bounded while retaining enough resolution for interactive zoom.
                scale = min(1.0, 5000.0 / max(ds.width, ds.height))
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
            self.info.setText(
                f"GeoTIFF: {Path(path).name} — rotella mouse = zoom, trascinamento = pan"
            )
            self._redraw()
            self.fit_map()
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

    def set_track_visibility(self, name: str, visible: bool) -> None:
        self._visible[name] = visible
        if self._pixmap is not None:
            self._redraw()

    def fit_map(self) -> None:
        if self._pixmap is None:
            return
        self.view.resetTransform()
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _gps_to_pixel(self, lon: float, lat: float) -> tuple[float, float]:
        if self._transformer is None or self._transform is None:
            raise RuntimeError("GeoTIFF non inizializzato.")
        x, y = self._transformer.transform(lon, lat)
        col, row = (~self._transform) * (x, y)
        return float(col), float(row)

    def _redraw(self) -> None:
        # Preserve current interactive zoom/pan transform while updating tracks.
        current_transform = self.view.transform()
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
            if not self._visible.get(name, True):
                continue

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

        self.view.setTransform(current_transform)
