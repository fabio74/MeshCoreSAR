from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

from models import Contact

# Companion Protocol commands / responses
CMD_APP_START = 0x01
CMD_GET_CONTACTS = 0x04
CMD_SET_DEVICE_TIME = 0x06
CMD_DEVICE_QUERY = 0x16
CMD_SEND_TELEMETRY_REQ = 0x27

RESP_CODE_ERR = 0x01
RESP_CODE_CONTACTS_START = 0x02
RESP_CODE_CONTACT = 0x03
RESP_CODE_END_OF_CONTACTS = 0x04
RESP_CODE_SELF_INFO = 0x05
RESP_CODE_SENT = 0x06
RESP_CODE_DEVICE_INFO = 0x0D

PUSH_CODE_TELEMETRY_RESPONSE = 0x8B

USB_TO_RADIO = ord("<")
USB_FROM_RADIO = ord(">")


def build_app_start(app_name: str = "MeshCoreTracker", protocol_version: int = 3) -> bytes:
    return bytes([CMD_APP_START, protocol_version]) + bytes(6) + app_name.encode("utf-8")


def build_device_query(protocol_version: int = 3) -> bytes:
    return bytes([CMD_DEVICE_QUERY, protocol_version])


def build_set_device_time(epoch_seconds: int) -> bytes:
    return bytes([CMD_SET_DEVICE_TIME]) + struct.pack("<I", epoch_seconds)


def build_get_contacts() -> bytes:
    return bytes([CMD_GET_CONTACTS])


def build_telemetry_request(public_key: bytes) -> bytes:
    if len(public_key) != 32:
        raise ValueError("La public key MeshCore deve essere di 32 byte.")
    return bytes([CMD_SEND_TELEMETRY_REQ, 0, 0, 0]) + public_key


def encode_usb_frame(payload: bytes) -> bytes:
    """App -> radio: '<' + uint16_le(length) + payload."""
    if len(payload) > 0xFFFF:
        raise ValueError("Frame troppo grande.")
    return bytes([USB_TO_RADIO]) + struct.pack("<H", len(payload)) + payload


class UsbFrameParser:
    """Incremental parser for radio -> app frames: '>' + uint16_le(length) + payload."""

    def __init__(self) -> None:
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        frames: list[bytes] = []

        while True:
            # Re-sync on the outbound marker from radio.
            marker = self.buffer.find(bytes([USB_FROM_RADIO]))
            if marker < 0:
                self.buffer.clear()
                break
            if marker > 0:
                del self.buffer[:marker]

            if len(self.buffer) < 3:
                break

            length = struct.unpack_from("<H", self.buffer, 1)[0]
            total = 3 + length
            if len(self.buffer) < total:
                break

            frames.append(bytes(self.buffer[3:total]))
            del self.buffer[:total]

        return frames


def _decode_c_string(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def decode_contact(frame: bytes) -> Contact:
    """Decode RESP_CODE_CONTACT (0x03). Current documented layout is 148 bytes incl. code."""
    if not frame or frame[0] != RESP_CODE_CONTACT:
        raise ValueError("Non è un frame RESP_CODE_CONTACT.")
    if len(frame) < 148:
        raise ValueError(f"Frame contatto troppo corto: {len(frame)} byte.")

    public_key = frame[1:33]
    adv_type = frame[33]
    flags = frame[34]
    out_path_len = struct.unpack("b", frame[35:36])[0]
    name = _decode_c_string(frame[100:132])
    last_advert = struct.unpack_from("<I", frame, 132)[0]
    adv_lat_i = struct.unpack_from("<i", frame, 136)[0]
    adv_lon_i = struct.unpack_from("<i", frame, 140)[0]
    lastmod = struct.unpack_from("<I", frame, 144)[0]

    return Contact(
        public_key=public_key,
        name=name or public_key[:6].hex(),
        adv_type=adv_type,
        flags=flags,
        out_path_len=out_path_len,
        last_advert=last_advert,
        adv_lat=adv_lat_i / 1_000_000 if adv_lat_i else None,
        adv_lon=adv_lon_i / 1_000_000 if adv_lon_i else None,
        lastmod=lastmod,
    )


def _signed_int24_be(raw: bytes) -> int:
    value = int.from_bytes(raw, "big", signed=False)
    if value & 0x800000:
        value -= 1 << 24
    return value


# Common Cayenne LPP type data lengths (not including channel + type bytes).
# This lets the parser safely skip types not used by the UI.
LPP_LENGTHS: dict[int, int] = {
    0x00: 1,  # digital input
    0x01: 1,  # digital output
    0x02: 2,  # analog input
    0x03: 2,  # analog output
    0x65: 2,  # luminosity
    0x66: 1,  # presence
    0x67: 2,  # temperature
    0x68: 1,  # humidity
    0x71: 6,  # accelerometer
    0x73: 2,  # barometer
    0x74: 2,  # voltage in the T1000e telemetry observed in this project
    0x86: 6,  # gyrometer
    0x88: 9,  # GPS
}


def decode_cayenne_lpp(payload: bytes) -> dict[str, Any]:
    """
    Decode the telemetry types needed by the tracker.
    Cayenne LPP multi-byte sensor values are big-endian.
    Repeated temperature values are retained in a list.
    """
    result: dict[str, Any] = {
        "temperatures_c": [],
        "unknown": [],
    }

    i = 0
    while i + 2 <= len(payload):
        channel = payload[i]
        data_type = payload[i + 1]
        i += 2

        length = LPP_LENGTHS.get(data_type)
        if length is None or i + length > len(payload):
            result["unknown"].append({
                "channel": channel,
                "type": data_type,
                "remaining_hex": payload[i:].hex(),
            })
            break

        raw = payload[i:i + length]
        i += length

        if data_type == 0x88 and len(raw) == 9:
            lat = _signed_int24_be(raw[0:3]) / 10000.0
            lon = _signed_int24_be(raw[3:6]) / 10000.0
            alt = _signed_int24_be(raw[6:9]) / 100.0
            result["gps"] = {
                "channel": channel,
                "latitude": lat,
                "longitude": lon,
                "altitude_m": alt,
            }
        elif data_type == 0x74:
            result["voltage_v"] = int.from_bytes(raw, "big", signed=False) / 100.0
        elif data_type == 0x65:
            result["luminosity_lux"] = int.from_bytes(raw, "big", signed=False)
        elif data_type == 0x67:
            result["temperatures_c"].append(
                int.from_bytes(raw, "big", signed=True) / 10.0
            )
        elif data_type == 0x68:
            result["humidity_percent"] = raw[0] / 2.0
        elif data_type == 0x73:
            result["barometer_hpa"] = int.from_bytes(raw, "big", signed=False) / 10.0
        else:
            result.setdefault("other", []).append({
                "channel": channel,
                "type": data_type,
                "raw_hex": raw.hex(),
            })

    return result


@dataclass(slots=True)
class TelemetryResponse:
    public_key_prefix: bytes
    lpp_payload: bytes
    decoded: dict[str, Any]


def decode_telemetry_response(frame: bytes) -> TelemetryResponse:
    if len(frame) < 8 or frame[0] != PUSH_CODE_TELEMETRY_RESPONSE:
        raise ValueError("Non è una PUSH_CODE_TELEMETRY_RESPONSE valida.")
    prefix = frame[2:8]
    lpp = frame[8:]
    return TelemetryResponse(
        public_key_prefix=prefix,
        lpp_payload=lpp,
        decoded=decode_cayenne_lpp(lpp),
    )
