import asyncio
import struct
from datetime import datetime
from bleak import BleakClient

ADDRESS = "F5:F9:AE:CC:95:2B"
RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

CMD_APP_START = bytes.fromhex("01 03 00 00 00 00 00 00 6D 63 63 6C 69")
CMD_GET_CONTACTS = bytes([0x04])
CMD_SEND_STATUS_REQ = 0x1B
CMD_SEND_TELEMETRY_REQ = 0x27

RESP_SELF_INFO = 0x05
RESP_CONTACTS_START = 0x02
RESP_CONTACT = 0x03
RESP_END_CONTACTS = 0x04
RESP_SENT = 0x06
TELEMETRY_CODE = 0x8B

TARGET_NAMES = {"GaucsFig1", "GaucsFig2"}


def hx(data):
    return " ".join(f"{x:02X}" for x in data)


def ascii_safe(data):
    return "".join(chr(x) if 32 <= x <= 126 else "." for x in data)


def u16le(data, off):
    return struct.unpack_from("<H", data, off)[0] if off + 2 <= len(data) else None


def i16le(data, off):
    return struct.unpack_from("<h", data, off)[0] if off + 2 <= len(data) else None


def u32le(data, off):
    return struct.unpack_from("<I", data, off)[0] if off + 4 <= len(data) else None


def i32le(data, off):
    return struct.unpack_from("<i", data, off)[0] if off + 4 <= len(data) else None


def parse_contact(frame):
    if len(frame) != 148 or frame[0] != RESP_CONTACT:
        return None
    payload = frame[1:]
    key = payload[:32]
    name = payload[99:131].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    return {"name": name, "public_key": key, "raw": frame}


def analyze_telemetry(frame, name=None):
    print()
    print("=" * 78)
    print("ANALISI TELEMETRIA 0x8B", name or "")
    print("=" * 78)
    print("Timestamp:", datetime.now().isoformat(timespec="milliseconds"))
    print("LEN:", len(frame))
    print("HEX:")
    print(hx(frame))
    print()
    print("ASCII:")
    print(ascii_safe(frame))

    if len(frame) >= 34:
        print()
        print("PUBLIC KEY:")
        print(hx(frame[2:34]))

    print()
    print("TABELLA BYTE / INTERI LITTLE-ENDIAN")
    print("-" * 78)
    print(f"{'OFF':>4} {'HEX':>4} {'U8':>5} {'U16LE':>8} {'I16LE':>8} {'U32LE':>12} {'I32LE':>12}")

    for off, b in enumerate(frame):
        print(
            f"{off:4d} {b:02X} {b:5d} "
            f"{u16le(frame, off) if u16le(frame, off) is not None else '':>8} "
            f"{i16le(frame, off) if i16le(frame, off) is not None else '':>8} "
            f"{u32le(frame, off) if u32le(frame, off) is not None else '':>12} "
            f"{i32le(frame, off) if i32le(frame, off) is not None else '':>12}"
        )


class Analyzer:
    def __init__(self):
        self.contacts = {}
        self.telemetry = {}
        self.end_contacts = asyncio.Event()
        self.telemetry_events = {}

    def handler(self, sender, data):
        frame = bytes(data)
        if not frame:
            return

        code = frame[0]
        print()
        print("#" * 78)
        print("FRAME RICEVUTO")
        print("#" * 78)
        print("Timestamp:", datetime.now().isoformat(timespec="milliseconds"))
        print("LEN:", len(frame))
        print("CODE:", f"0x{code:02X}")
        print("HEX:")
        print(hx(frame))

        if code == RESP_SELF_INFO:
            print("RESP_CODE_SELF_INFO")
        elif code == RESP_CONTACTS_START:
            print("RESP_CODE_CONTACTS_START")
        elif code == RESP_CONTACT:
            contact = parse_contact(frame)
            if contact:
                self.contacts[contact["name"]] = contact
                print("RESP_CODE_CONTACT")
                print("Nome:", contact["name"])
                print("PublicKey:", hx(contact["public_key"]))
        elif code == RESP_END_CONTACTS:
            print("RESP_CODE_END_OF_CONTACTS")
            self.end_contacts.set()
        elif code == RESP_SENT:
            print("RESP_CODE_SENT")
        elif code == TELEMETRY_CODE:
            print("PUSH_CODE_TELEMETRY_RESPONSE")
            key = frame[2:34] if len(frame) >= 34 else b""
            name = next(
                (n for n, c in self.contacts.items() if c["public_key"] == key),
                None
            )
            self.telemetry[name or key.hex()] = frame
            analyze_telemetry(frame, name)
            if name in self.telemetry_events:
                self.telemetry_events[name].set()
        else:
            print("CODICE NON DECODIFICATO")


async def main():
    print("=" * 78)
    print("       MESHCORE - TELEMETRY ANALYZER")
    print("=" * 78)

    analyzer = Analyzer()
    client = BleakClient(ADDRESS)
    tx = None

    try:
        print("Connessione BLE...")
        await client.connect()
        print("Connesso:", client.is_connected)

        rx = None
        for service in client.services:
            for char in service.characteristics:
                uuid = str(char.uuid).lower()
                if uuid == RX_UUID:
                    rx = char
                elif uuid == TX_UUID:
                    tx = char

        if rx is None or tx is None:
            raise RuntimeError("Caratteristiche MeshCore RX/TX non trovate")

        print("RX:", rx.uuid)
        print("TX:", tx.uuid)

        await client.start_notify(tx, analyzer.handler)
        print("Notify TX: OK")
        await asyncio.sleep(0.5)

        print()
        print("1) CMD_APP_START")
        await client.write_gatt_char(rx, CMD_APP_START, response=False)
        await asyncio.sleep(2)

        print()
        print("2) CMD_GET_CONTACTS")
        await client.write_gatt_char(rx, CMD_GET_CONTACTS, response=False)

        try:
            await asyncio.wait_for(analyzer.end_contacts.wait(), timeout=15)
        except asyncio.TimeoutError:
            print("Timeout lista contatti.")

        print()
        print("=" * 78)
        print("CONTATTI")
        print("=" * 78)
        for name, contact in analyzer.contacts.items():
            print(f"{name:30s} {contact['public_key'].hex()}")

        for name in TARGET_NAMES:
            contact = analyzer.contacts.get(name)
            if not contact:
                print("Contatto non trovato:", name)
                continue

            key = contact["public_key"]

            print()
            print("=" * 78)
            print("TEST:", name)
            print("=" * 78)

            status = bytes([CMD_SEND_STATUS_REQ]) + key
            print("CMD_SEND_STATUS_REQ:", hx(status))
            await client.write_gatt_char(rx, status, response=False)
            await asyncio.sleep(2)

            telemetry = bytes([CMD_SEND_TELEMETRY_REQ, 0x00, 0x00, 0x00]) + key
            analyzer.telemetry_events[name] = asyncio.Event()

            print("CMD_SEND_TELEMETRY_REQ:", hx(telemetry))
            await client.write_gatt_char(rx, telemetry, response=False)

            try:
                await asyncio.wait_for(
                    analyzer.telemetry_events[name].wait(),
                    timeout=30
                )
            except asyncio.TimeoutError:
                print("TIMEOUT telemetria:", name)

            await asyncio.sleep(1)

        print()
        print("=" * 78)
        print("CONFRONTO TELEMETRIA")
        print("=" * 78)

        frames = [
            (n, f) for n, f in analyzer.telemetry.items()
            if n in TARGET_NAMES
        ]

        if len(frames) >= 2:
            (n1, a), (n2, b) = frames[:2]
            print(n1, "LEN =", len(a))
            print(n2, "LEN =", len(b))
            print()
            print(f"{'OFF':>4} {'A':>4} {'B':>4} STATO")
            print("-" * 30)
            for i in range(max(len(a), len(b))):
                av = a[i] if i < len(a) else None
                bv = b[i] if i < len(b) else None
                print(
                    f"{i:4d} "
                    f"{('--' if av is None else f'{av:02X}'):>4} "
                    f"{('--' if bv is None else f'{bv:02X}'):>4} "
                    f"{'UGUALE' if av == bv else 'DIVERSO'}"
                )
        else:
            print("Servono almeno due frame 0x8B associati.")

    except Exception as e:
        print()
        print("=" * 78)
        print("ERRORE")
        print("=" * 78)
        print(type(e).__name__, ":", str(e))

    finally:
        try:
            if client.is_connected and tx is not None:
                await client.stop_notify(tx)
        except Exception:
            pass
        try:
            if client.is_connected:
                await client.disconnect()
        except Exception:
            pass
        print("Bluetooth disconnesso.")


if __name__ == "__main__":
    asyncio.run(main())
