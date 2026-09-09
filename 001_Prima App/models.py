from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Contact:
    public_key: bytes
    name: str
    adv_type: int = 0
    flags: int = 0
    out_path_len: int = 0
    last_advert: int = 0
    adv_lat: float | None = None
    adv_lon: float | None = None
    lastmod: int = 0

    @property
    def key_hex(self) -> str:
        return self.public_key.hex()

    @property
    def prefix(self) -> bytes:
        return self.public_key[:6]


@dataclass(slots=True)
class TelemetryPoint:
    timestamp: datetime
    contact_name: str
    latitude: float
    longitude: float
    altitude_m: float | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)
