from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from models import TelemetryPoint


class CsvSessionLogger:
    HEADER = [
        "timestamp",
        "contact",
        "latitude",
        "longitude",
        "altitude_m",
        "voltage_v",
        "luminosity_lux",
        "temperature_1_c",
        "temperature_2_c",
        "humidity_percent",
        "barometer_hpa",
        "lpp_hex",
    ]

    def __init__(self, base_dir: str | Path = "data") -> None:
        self.base_dir = Path(base_dir)
        self.session_started = datetime.now()
        self._paths: dict[str, Path] = {}

    def new_session(self) -> None:
        self.session_started = datetime.now()
        self._paths.clear()

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*]+', "_", name).strip(" .")
        return cleaned or "contact"

    def _path_for(self, contact_name: str) -> Path:
        if contact_name in self._paths:
            return self._paths[contact_name]

        day_dir = self.base_dir / self.session_started.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            self.session_started.strftime("%Y-%m-%d_%H-%M-%S")
            + "_"
            + self._safe_name(contact_name)
            + ".csv"
        )
        path = day_dir / filename
        self._paths[contact_name] = path
        return path

    def append(self, point: TelemetryPoint, lpp_hex: str = "") -> Path:
        path = self._path_for(point.contact_name)
        first_write = not path.exists()
        temps = point.telemetry.get("temperatures_c", [])

        row = {
            "timestamp": point.timestamp.astimezone().isoformat(timespec="seconds"),
            "contact": point.contact_name,
            "latitude": f"{point.latitude:.6f}",
            "longitude": f"{point.longitude:.6f}",
            "altitude_m": "" if point.altitude_m is None else f"{point.altitude_m:.2f}",
            "voltage_v": point.telemetry.get("voltage_v", ""),
            "luminosity_lux": point.telemetry.get("luminosity_lux", ""),
            "temperature_1_c": temps[0] if len(temps) > 0 else "",
            "temperature_2_c": temps[1] if len(temps) > 1 else "",
            "humidity_percent": point.telemetry.get("humidity_percent", ""),
            "barometer_hpa": point.telemetry.get("barometer_hpa", ""),
            "lpp_hex": lpp_hex,
        }

        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=self.HEADER)
            if first_write:
                writer.writeheader()
            writer.writerow(row)

        return path
