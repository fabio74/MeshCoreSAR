from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


def _to_gpx_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def export_tracks_gpx(tracks: dict[str, list[dict]], output_path: str | Path) -> Path:
    """Export all recorded tracks to a GPX 1.1 file, one <trk> per device."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gpx = ET.Element(
        "gpx",
        {
            "version": "1.1",
            "creator": "MeshCore Tracker",
            "xmlns": "http://www.topografix.com/GPX/1/1",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "http://www.topografix.com/GPX/1/1 "
                "http://www.topografix.com/GPX/1/1/gpx.xsd"
            ),
        },
    )

    metadata = ET.SubElement(gpx, "metadata")
    ET.SubElement(metadata, "name").text = "MeshCore Tracker"
    ET.SubElement(metadata, "time").text = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    for name in sorted(tracks):
        points = tracks[name]
        if not points:
            continue

        trk = ET.SubElement(gpx, "trk")
        ET.SubElement(trk, "name").text = name
        seg = ET.SubElement(trk, "trkseg")

        for point in points:
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is None or lon is None:
                continue

            trkpt = ET.SubElement(
                seg,
                "trkpt",
                {"lat": f"{float(lat):.8f}", "lon": f"{float(lon):.8f}"},
            )
            alt = point.get("alt")
            if alt is not None:
                ET.SubElement(trkpt, "ele").text = f"{float(alt):.2f}"

            gpx_time = _to_gpx_time(point.get("timestamp"))
            if gpx_time:
                ET.SubElement(trkpt, "time").text = gpx_time

    tree = ET.ElementTree(gpx)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path
