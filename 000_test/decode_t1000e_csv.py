import asyncio
import struct
import csv
import re
import time
from pathlib import Path
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
RESP_END_OF_CONTACTS = 0x04
RESP_SENT = 0x06
PUSH_TELEMETRY = 0x8B

TARGET_NAMES = ["GaucsFig1", "GaucsFig2", "GaucsFig3"]
#TARGET_NAMES = ["GaucsFig3"]


def safe_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "SCONOSCIUTO"


class CSVLogger:
    def __init__(self):
        self.files = {}
        self.writers = {}

    def write(self, contact, timestamp, frame, values):
        if contact not in self.files:
            start_dt = datetime.now()
            filename = f"{start_dt:%Y-%m-%d}_{safe_filename(contact)}.csv"
            path = Path(filename)
            f = path.open("a", newline="", encoding="utf-8-sig")
            writer = csv.writer(f, delimiter=";")
            #writer.writerow([
            #    "timestamp", "contatto", "tensione_V",
            #    "latitudine", "longitudine", "altitudine_m",
            #    "luce_lux", "temperatura_C", "umidita_percent",
            #    "accelerometro_X_g", "accelerometro_Y_g", "accelerometro_Z_g",
            #    "frame_hex", "lpp_hex"
            #])
            self.files[contact] = (f, path)
            self.writers[contact] = writer
            print(f"CSV creato: {path.resolve()}")

        f, path = self.files[contact]
        writer = self.writers[contact]

        gps = []
        voltage = []
        light = []
        temp = []
        humidity = []
        accel = []

        for ch, typ, name, value in values:
            if name == "gps":
                gps.append(value)
            elif name == "voltage_v":
                voltage.append(value)
            elif name == "illuminance_lux":
                light.append(value)
            elif name == "temperature_c":
                temp.append(value)
            elif name == "humidity_percent":
                humidity.append(value)
            elif name == "accelerometer_g":
                accel.append(value)

        lat = lon = alt = ""
        if gps:
            lat, lon, alt = gps[-1]

        ax = ay = az = ""
        if accel:
            ax, ay, az = accel[-1]

        writer.writerow([
            timestamp,
            contact,
            f"{lat:.6f}" if lat != "" else "",
            f"{lon:.6f}" if lon != "" else "",
            f"{alt:.2f}" if alt != "" else "",
            "|".join(str(v) for v in light),
            "|".join(f"{v:.1f}" for v in temp),
            "|".join(f"{v:.1f}" for v in humidity),
            "|".join(f"{v:.2f}" for v in voltage)
            #f"{ax:.3f}" if ax != "" else "",
            #f"{ay:.3f}" if ay != "" else "",
            #f"{az:.3f}" if az != "" else "",
            #hx(frame),
            #hx(frame[8:])
        ])
        f.flush()

    def close(self):
        for f, _ in self.files.values():
            f.close()


def hx(data):
    return " ".join(f"{b:02X}" for b in data)


def signed24_be(data):
    v = int.from_bytes(data, "big", signed=False)
    return v - 0x1000000 if v & 0x800000 else v


def decode_lpp(payload):
    out = []
    i = 0

    while i + 2 <= len(payload):
        ch, typ = payload[i], payload[i + 1]
        i += 2

        if typ in (0x00, 0x01, 0x66):
            if i + 1 > len(payload): break
            value = payload[i]
            i += 1
            names = {0x00: "digital_input", 0x01: "digital_output", 0x66: "presence"}
            out.append((ch, typ, names[typ], value))

        elif typ in (0x02, 0x03):
            if i + 2 > len(payload): break
            value = struct.unpack(">h", payload[i:i+2])[0] / 100.0
            i += 2
            out.append((ch, typ, "analog", value))

        elif typ == 0x65:
            if i + 2 > len(payload): break
            value = struct.unpack(">H", payload[i:i+2])[0]
            i += 2
            out.append((ch, typ, "illuminance_lux", value))

        elif typ == 0x67:
            if i + 2 > len(payload): break
            value = struct.unpack(">h", payload[i:i+2])[0] / 10.0
            i += 2
            out.append((ch, typ, "temperature_c", value))

        elif typ == 0x68:
            if i + 1 > len(payload): break
            value = payload[i] / 2.0
            i += 1
            out.append((ch, typ, "humidity_percent", value))

        elif typ == 0x73:
            if i + 6 > len(payload): break
            x, y, z = struct.unpack(">hhh", payload[i:i+6])
            i += 6
            out.append((ch, typ, "accelerometer_g",
                        (x/1000.0, y/1000.0, z/1000.0)))

        elif typ == 0x74:
            if i + 2 > len(payload): break
            value = struct.unpack(">H", payload[i:i+2])[0] / 100.0
            i += 2
            out.append((ch, typ, "voltage_v", value))

        elif typ in (0x77, 0x88, 0x99, 0x9A):
            # MeshCore/T1000-E samples observed use 0x88.
            if i + 9 > len(payload): break
            lat = signed24_be(payload[i:i+3]) / 10000.0
            lon = signed24_be(payload[i+3:i+6]) / 10000.0
            alt = signed24_be(payload[i+6:i+9]) / 100.0
            i += 9
            out.append((ch, typ, "gps", (lat, lon, alt)))

        elif typ == 0x86:
            if i + 6 > len(payload): break
            x, y, z = struct.unpack(">hhh", payload[i:i+6])
            i += 6
            out.append((ch, typ, "gyrometer", (x/100.0, y/100.0, z/100.0)))

        else:
            print(f"Tipo LPP non gestito: 0x{typ:02X} all'offset {i-2}")
            break

    return out


def decode_contact(frame):
    if len(frame) != 148 or frame[0] != RESP_CONTACT:
        return None
    payload = frame[1:]
    name = payload[99:131].split(b"\x00", 1)[0].decode("utf-8", "replace")
    return {"name": name, "public_key": payload[:32]}


def print_telemetry(frame, contacts, csv_logger=None):
    if len(frame) < 8 or frame[0] != PUSH_TELEMETRY:
        return None

    prefix = frame[2:8]
    contact = next(
        (name for name, c in contacts.items() if c["public_key"][:6] == prefix),
        "SCONOSCIUTO"
    )
    lpp = frame[8:]
    values = decode_lpp(lpp)

    print()
    print("=" * 78)
    print("PUSH_CODE_TELEMETRY_RESPONSE 0x8B")
    print("=" * 78)
    print("Contatto :", contact)
    timestamp = datetime.now().isoformat(timespec="milliseconds")
    print("Timestamp:", timestamp)
    print("Frame HEX:")
    print(hx(frame))
    print("LPP HEX:")
    print(hx(lpp))
    print("-" * 78)

    for ch, typ, name, value in values:
        if name == "gps":
            lat, lon, alt = value
            print(f"GPS        CH={ch}: {lat:.6f}, {lon:.6f}, alt {alt:.2f} m")
        elif name == "temperature_c":
            print(f"TEMPERATURA CH={ch}: {value:.1f} °C")
        elif name == "voltage_v":
            print(f"TENSIONE   CH={ch}: {value:.2f} V")
        elif name == "illuminance_lux":
            print(f"LUCE       CH={ch}: {value} lux")
        elif name == "humidity_percent":
            print(f"UMIDITA    CH={ch}: {value:.1f} %")
        elif name == "accelerometer_g":
            x, y, z = value
            print(f"ACCEL      CH={ch}: X={x:.3f} Y={y:.3f} Z={z:.3f} g")
        else:
            print(f"{name.upper():12s} CH={ch}: {value}")

    if csv_logger is not None:
        csv_logger.write(contact, timestamp, frame, values)

    return contact, values


class Analyzer:
    def __init__(self):
        self.contacts = {}
        self.end_contacts = asyncio.Event()
        self.telemetry_events = {}
        self.csv_logger = CSVLogger()

    def callback(self, sender, data):
        frame = bytes(data)
        if not frame:
            return

        print()
        print("#" * 78)
        print("FRAME RICEVUTO")
        print("#" * 78)
        timestamp = datetime.now().isoformat(timespec="milliseconds")
        print("Timestamp:", timestamp)
        print("LEN:", len(frame))
        print("CODE:", f"0x{frame[0]:02X}")
        print("HEX:", hx(frame))

        code = frame[0]

        if code == RESP_SELF_INFO:
            print("-> RESP_CODE_SELF_INFO")

        elif code == RESP_CONTACTS_START:
            print("-> RESP_CODE_CONTACTS_START")

        elif code == RESP_CONTACT:
            c = decode_contact(frame)
            if c:
                self.contacts[c["name"]] = c
                print("-> RESP_CODE_CONTACT")
                print("Nome:", c["name"])
                print("Public key:", hx(c["public_key"]))

        elif code == RESP_END_OF_CONTACTS:
            print("-> RESP_CODE_END_OF_CONTACTS")
            self.end_contacts.set()

        elif code == RESP_SENT:
            print("-> RESP_CODE_SENT")

        elif code == PUSH_TELEMETRY:
            result = print_telemetry(frame, self.contacts, self.csv_logger)
            if result:
                name, _ = result
                event = self.telemetry_events.get(name)
                if event:
                    event.set()

        else:
            print("-> CODICE NON DECODIFICATO")


async def main():

    try:
        passo = 1
        while True:

            print("=" * 78)
            print("       MESHCORE - SENSECAP T1000-E DECODER")
            print("=" * 78)

            analyzer = Analyzer()
            client = BleakClient(ADDRESS)
            rx = tx = None

            try:
                print("Connessione BLE...")
                await client.connect()
                print("Connesso:", client.is_connected)

                for service in client.services:
                    for char in service.characteristics:
                        u = str(char.uuid).lower()
                        if u == RX_UUID:
                            rx = char
                        elif u == TX_UUID:
                            tx = char

                if rx is None or tx is None:
                    raise RuntimeError("RX/TX MeshCore non trovate")

                print("RX:", rx.uuid)
                print("TX:", tx.uuid)

                await client.start_notify(tx, analyzer.callback)
                print("Notify TX: OK")
                await asyncio.sleep(0.5)

                print()
                print("1) CMD_APP_START")
                print(hx(CMD_APP_START))
                await client.write_gatt_char(rx, CMD_APP_START, response=False)
                await asyncio.sleep(2)

                print()
                print("2) CMD_GET_CONTACTS")
                print(hx(CMD_GET_CONTACTS))
                await client.write_gatt_char(rx, CMD_GET_CONTACTS, response=False)

                try:
                    await asyncio.wait_for(analyzer.end_contacts.wait(), timeout=20)
                except asyncio.TimeoutError:
                    print("Timeout GET_CONTACTS")

                print()
                print("=" * 78)
                print("CONTATTI TROVATI")
                print("=" * 78)
                for n, c in analyzer.contacts.items():
                    print(f"{n:30s} {c['public_key'].hex()}")

                for target in TARGET_NAMES:
                    c = analyzer.contacts.get(target)

                    print()
                    print("=" * 78)
                    print("RICHIESTA TELEMETRIA:", target)
                    print("=" * 78)

                    if not c:
                        print("Contatto non trovato.")
                        continue

                    key = c["public_key"]

                    status = bytes([CMD_SEND_STATUS_REQ]) + key
                    print("STATUS REQ:", hx(status))
                    await client.write_gatt_char(rx, status, response=False)
                    await asyncio.sleep(2)

                    analyzer.telemetry_events[target] = asyncio.Event()

                    # CMD_SEND_TELEMETRY_REQ = 0x27.
                    # Formato utilizzato nel test precedente: 27 00 00 00 + 32-byte public key.
                    request = bytes([CMD_SEND_TELEMETRY_REQ, 0x00, 0x00, 0x00]) + key
                    print("TELEMETRY REQ:", hx(request))
                    await client.write_gatt_char(rx, request, response=False)

                    try:
                        await asyncio.wait_for(
                            analyzer.telemetry_events[target].wait(),
                            timeout=30
                        )
                    except asyncio.TimeoutError:
                        print("TIMEOUT telemetria:", target)

                    await asyncio.sleep(1)

                print()
                print("=" * 78)
                print("TEST TERMINATO")
                print("=" * 78)

            except Exception as e:
                print()
                print("=" * 78)
                print("ERRORE")
                print("=" * 78)
                print(type(e).__name__, ":", str(e))

            finally:
                analyzer.csv_logger.close()
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

            print("Attesa 1 secondi.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgramma interrotto correttamente con Ctrl+C.")


if __name__ == "__main__":
    asyncio.run(main())
