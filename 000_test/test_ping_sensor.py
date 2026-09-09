import asyncio
import struct
from datetime import datetime

from bleak import BleakClient


# ============================================================
# CONFIGURAZIONE GAUCS
# ============================================================

ADDRESS = "F5:F9:AE:CC:95:2B"

RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
TX_UUID = "6E400003-B5A3-F393-E0A9-E50E"


# ============================================================
# MESHCORE COMPANION PROTOCOL
# ============================================================

CMD_APP_START = 0x01
CMD_GET_CONTACTS = 0x04

# Non esiste un PING vero e proprio:
# usiamo STATUS_REQ come verifica del contatto.
CMD_SEND_STATUS_REQ = 0x1B

# Richiesta telemetria.
CMD_SEND_TELEMETRY_REQ = 0x27


# Risposte
RESP_CODE_OK = 0x00
RESP_CODE_ERR = 0x01

RESP_CODE_CONTACTS_START = 0x02
RESP_CODE_CONTACT = 0x03
RESP_CODE_END_OF_CONTACTS = 0x04

RESP_CODE_SELF_INFO = 0x05
RESP_CODE_SENT = 0x06

PUSH_CODE_STATUS_RESPONSE = 0x87
PUSH_CODE_TELEMETRY_RESPONSE = 0x8B


# ============================================================
# CONTATTI DA TESTARE
# ============================================================

TARGET_NAMES = [
    "GaucsFig1",
    "GaucsFig2",
]


# ============================================================
# APP START
# ============================================================

APP_START = bytes([
    CMD_APP_START,
    0x03,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
]) + b"mccli"


# ============================================================
# UTILITY
# ============================================================

def hex_dump(data):
    return data.hex(" ")


def ascii_dump(data):
    return "".join(
        chr(x) if 32 <= x <= 126 else "."
        for x in data
    )


def u16_be(data, offset):
    if len(data) < offset + 2:
        return None

    return struct.unpack_from(">H", data, offset)[0]


def u32_le(data, offset):
    if len(data) < offset + 4:
        return None

    return struct.unpack_from("<I", data, offset)[0]


# ============================================================
# CONTATTO
# ============================================================

def decode_contact(data):

    if len(data) != 148:
        print(
            f"ATTENZIONE: CONTACT di {len(data)} byte "
            f"invece di 148"
        )

    if len(data) < 148:
        return None

    public_key = data[1:33]

    contact_type = data[33]

    flags = data[34]

    path_len = struct.unpack(
        "<b",
        bytes([data[35]])
    )[0]

    name = (
        data[100:132]
        .split(b"\x00", 1)[0]
        .decode("utf-8", errors="replace")
    )

    last_advert = u32_le(data, 132)

    latitude_raw = struct.unpack_from(
        "<i",
        data,
        136
    )[0]

    longitude_raw = struct.unpack_from(
        "<i",
        data,
        140
    )[0]

    lastmod = u32_le(data, 144)

    return {
        "name": name,
        "public_key": public_key,
        "public_key_hex": public_key.hex(),
        "type": contact_type,
        "flags": flags,
        "path_len": path_len,
        "last_advert": last_advert,
        "latitude": latitude_raw / 1_000_000,
        "longitude": longitude_raw / 1_000_000,
        "lastmod": lastmod,
    }


# ============================================================
# DECODIFICA STATUS RESPONSE
# ============================================================

def decode_status_response(data):

    print()
    print("-" * 70)
    print("PUSH_CODE_STATUS_RESPONSE")
    print("-" * 70)

    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    if len(data) >= 8:

        prefix = data[2:8]

        print()
        print("Public Key prefix:")
        print(prefix.hex())

    if len(data) > 8:

        status_data = data[8:]

        print()
        print("STATUS DATA HEX:")
        print(hex_dump(status_data))

        print()
        print("STATUS DATA ASCII:")
        print(ascii_dump(status_data))

    return data


# ============================================================
# DECODIFICA TELEMETRIA
# ============================================================

def decode_telemetry(data):

    print()
    print("=" * 70)
    print("PUSH_CODE_TELEMETRY_RESPONSE")
    print("=" * 70)

    print()
    print("Timestamp:")
    print(
        datetime.now().isoformat(
            timespec="milliseconds"
        )
    )

    print()
    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    if len(data) < 8:
        print("Frame telemetria troppo corto.")
        return

    prefix = data[2:8]

    print()
    print("Public Key prefix:")
    print(prefix.hex())

    lpp = data[8:]

    print()
    print("CayenneLPP RAW:")
    print(hex_dump(lpp))

    print()
    print("CayenneLPP LEN:")
    print(len(lpp))

    decode_cayenne_lpp(lpp)


# ============================================================
# CAYENNE LPP
# ============================================================

def decode_cayenne_lpp(data):

    print()
    print("-" * 70)
    print("DECODIFICA CAYENNE LPP")
    print("-" * 70)

    pos = 0

    while pos < len(data):

        if pos + 2 > len(data):
            break

        channel = data[pos]
        data_type = data[pos + 1]

        pos += 2

        print()
        print(
            f"Channel {channel} "
            f"Type 0x{data_type:02X}"
        )

        # ----------------------------------------------------
        # Digital Input
        # ----------------------------------------------------

        if data_type == 0x00:

            if pos + 1 > len(data):
                break

            value = data[pos]

            pos += 1

            print(
                "  Digital Input:",
                value
            )

        # ----------------------------------------------------
        # Digital Output
        # ----------------------------------------------------

        elif data_type == 0x01:

            if pos + 1 > len(data):
                break

            value = data[pos]

            pos += 1

            print(
                "  Digital Output:",
                value
            )

        # ----------------------------------------------------
        # Analog Input
        # ----------------------------------------------------

        elif data_type == 0x02:

            if pos + 2 > len(data):
                break

            raw = u16_be(data, pos)

            if raw >= 32768:
                raw -= 65536

            pos += 2

            print(
                "  Analog Input:",
                raw / 100.0
            )

        # ----------------------------------------------------
        # Analog Output
        # ----------------------------------------------------

        elif data_type == 0x03:

            if pos + 2 > len(data):
                break

            raw = u16_be(data, pos)

            if raw >= 32768:
                raw -= 65536

            pos += 2

            print(
                "  Analog Output:",
                raw / 100.0
            )

        # ----------------------------------------------------
        # Temperature
        # ----------------------------------------------------

        elif data_type == 0x67:

            if pos + 2 > len(data):
                break

            raw = u16_be(data, pos)

            if raw >= 32768:
                raw -= 65536

            pos += 2

            temperature = raw / 10.0

            print(
                f"  Temperature: "
                f"{temperature:.1f} °C"
            )

        # ----------------------------------------------------
        # Relative Humidity
        # ----------------------------------------------------

        elif data_type == 0x68:

            if pos + 1 > len(data):
                break

            raw = data[pos]

            pos += 1

            humidity = raw / 2.0

            print(
                f"  Humidity: "
                f"{humidity:.1f} %"
            )

        # ----------------------------------------------------
        # GPS
        # Cayenne LPP:
        #
        # latitude  : 3 byte signed / 10000
        # longitude : 3 byte signed / 10000
        # altitude  : 3 byte signed / 100
        # ----------------------------------------------------

        elif data_type == 0x88:

            if pos + 9 > len(data):
                break

            lat_raw = (
                (data[pos] << 16)
                | (data[pos + 1] << 8)
                | data[pos + 2]
            )

            lon_raw = (
                (data[pos + 3] << 16)
                | (data[pos + 4] << 8)
                | data[pos + 5]
            )

            alt_raw = (
                (data[pos + 6] << 16)
                | (data[pos + 7] << 8)
                | data[pos + 8]
            )

            # sign extension 24 bit
            if lat_raw & 0x800000:
                lat_raw -= 0x1000000

            if lon_raw & 0x800000:
                lon_raw -= 0x1000000

            if alt_raw & 0x800000:
                alt_raw -= 0x1000000

            pos += 9

            latitude = lat_raw / 10000.0
            longitude = lon_raw / 10000.0
            altitude = alt_raw / 100.0

            print()
            print("  GPS:")
            print(
                f"    Latitude : {latitude:.6f}"
            )
            print(
                f"    Longitude: {longitude:.6f}"
            )
            print(
                f"    Altitude : {altitude:.2f} m"
            )

        # ----------------------------------------------------
        # Battery
        # Voltage
        # ----------------------------------------------------

        elif data_type == 0x02:

            if pos + 2 > len(data):
                break

            raw = u16_be(data, pos)

            if raw >= 32768:
                raw -= 65536

            pos += 2

            print(
                "  Analog value:",
                raw / 100.0
            )

        # ----------------------------------------------------
        # Unknown
        # ----------------------------------------------------

        else:

            print(
                "  Tipo LPP non decodificato."
            )

            print(
                "  Remaining HEX:",
                hex_dump(data[pos:])
            )

            break


# ============================================================
# SENSOR TEST
# ============================================================

class SensorTester:

    def __init__(self):

        self.contacts = {}

        self.status_event = None
        self.telemetry_event = None

        self.expected_prefix = None

        self.received_status = None
        self.received_telemetry = None

        self.contact_list_finished = asyncio.Event()

    # --------------------------------------------------------
    # BLE CALLBACK
    # --------------------------------------------------------

    def notification_handler(self, sender, data):

        data = bytes(data)

        if not data:
            return

        code = data[0]

        print()
        print()
        print("#" * 70)
        print("FRAME BLE RICEVUTO")
        print("#" * 70)

        print()
        print("Timestamp:")
        print(
            datetime.now().isoformat(
                timespec="milliseconds"
            )
        )

        print()
        print("HEX:")
        print(hex_dump(data))

        print()
        print("LEN:", len(data))

        print()
        print(
            "CODE:",
            f"0x{code:02X}"
        )

        # ----------------------------------------------------
        # SELF INFO
        # ----------------------------------------------------

        if code == RESP_CODE_SELF_INFO:

            print("RESP_CODE_SELF_INFO")

        # ----------------------------------------------------
        # CONTACT START
        # ----------------------------------------------------

        elif code == RESP_CODE_CONTACTS_START:

            print("RESP_CODE_CONTACTS_START")

        # ----------------------------------------------------
        # CONTACT
        # ----------------------------------------------------

        elif code == RESP_CODE_CONTACT:

            contact = decode_contact(data)

            if contact:

                self.contacts[
                    contact["name"]
                ] = contact

                print()
                print(
                    "CONTATTO:",
                    contact["name"]
                )

        # ----------------------------------------------------
        # CONTACT END
        # ----------------------------------------------------

        elif code == RESP_CODE_END_OF_CONTACTS:

            print(
                "RESP_CODE_END_OF_CONTACTS"
            )

            self.contact_list_finished.set()

        # ----------------------------------------------------
        # OK
        # ----------------------------------------------------

        elif code == RESP_CODE_OK:

            print(
                "RESP_CODE_OK"
            )

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        elif code == RESP_CODE_ERR:

            print(
                "RESP_CODE_ERR"
            )

            if len(data) > 1:

                print(
                    "Error code:",
                    f"0x{data[1]:02X}"
                )

        # ----------------------------------------------------
        # SENT
        # ----------------------------------------------------

        elif code == RESP_CODE_SENT:

            print(
                "RESP_CODE_SENT"
            )

            if len(data) >= 5:

                value = u32_le(data, 1)

                print(
                    "Value:",
                    value
                )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        elif code == PUSH_CODE_STATUS_RESPONSE:

            print(
                "PUSH_CODE_STATUS_RESPONSE"
            )

            self.received_status = data

            decode_status_response(data)

            if self.status_event:

                self.status_event.set()

        # ----------------------------------------------------
        # TELEMETRY
        # ----------------------------------------------------

        elif code == PUSH_CODE_TELEMETRY_RESPONSE:

            print(
                "PUSH_CODE_TELEMETRY_RESPONSE"
            )

            self.received_telemetry = data

            decode_telemetry(data)

            if self.telemetry_event:

                self.telemetry_event.set()

        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        else:

            print(
                "FRAME NON GESTITO"
            )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("       MESHCORE - SENSOR TEST")
    print("=" * 70)

    print()
    print("GAUCS:", ADDRESS)

    client = BleakClient(ADDRESS)

    tester = SensorTester()

    try:

        # ====================================================
        # CONNECT
        # ====================================================

        print()
        print("Connessione BLE...")

        await client.connect()

        print(
            "Connesso:",
            client.is_connected
        )

        if not client.is_connected:

            return

        # ====================================================
        # NOTIFY
        # ====================================================

        print()
        print("Attivazione notifiche TX...")

        await client.start_notify(
            TX_UUID,
            tester.notification_handler
        )

        print("Notify TX: OK")

        # ====================================================
        # APP START
        # ====================================================

        print()
        print("=" * 70)
        print("1. CMD_APP_START")
        print("=" * 70)

        print()
        print(
            "TX:",
            hex_dump(APP_START)
        )

        await client.write_gatt_char(
            RX_UUID,
            APP_START,
            response=False
        )

        await asyncio.sleep(1)

        # ====================================================
        # GET CONTACTS
        # ====================================================

        print()
        print("=" * 70)
        print("2. CMD_GET_CONTACTS")
        print("=" * 70)

        await client.write_gatt_char(
            RX_UUID,
            bytes([CMD_GET_CONTACTS]),
            response=False
        )

        print(
            "CMD_GET_CONTACTS inviato."
        )

        try:

            await asyncio.wait_for(
                tester.contact_list_finished.wait(),
                timeout=10
            )

        except asyncio.TimeoutError:

            print(
                "Timeout lista contatti."
            )

        # ====================================================
        # VERIFICA CONTATTI
        # ====================================================

        print()
        print("=" * 70)
        print("CONTATTI TARGET")
        print("=" * 70)

        targets = []

        for name in TARGET_NAMES:

            contact = tester.contacts.get(name)

            if contact is None:

                print()
                print(
                    f"ERRORE: {name} "
                    "non trovato."
                )

                continue

            targets.append(contact)

            print()
            print("Nome:")
            print(
                f"  {contact['name']}"
            )

            print("Public Key:")
            print(
                f"  {contact['public_key_hex']}"
            )

            print("Advert GPS:")
            print(
                f"  {contact['latitude']:.6f}, "
                f"{contact['longitude']:.6f}"
            )

        if not targets:

            print()
            print(
                "Nessun target trovato."
            )

            return

        # ====================================================
        # TEST SENSORI
        # ====================================================

        for contact in targets:

            name = contact["name"]

            public_key = contact["public_key"]

            prefix = public_key[:6]

            print()
            print()
            print("=" * 70)
            print(
                f"TEST SENSOR: {name}"
            )
            print("=" * 70)

            print()
            print("Public Key:")
            print(public_key.hex())

            print()
            print("Public Key prefix:")
            print(prefix.hex())

            # =================================================
            # STATUS REQUEST
            # =================================================

            print()
            print("-" * 70)
            print("STATUS REQUEST")
            print("-" * 70)

            status_command = (
                bytes([CMD_SEND_STATUS_REQ])
                + public_key
            )

            print()
            print("CMD_SEND_STATUS_REQ:")
            print(
                hex_dump(status_command)
            )

            tester.status_event = asyncio.Event()
            tester.received_status = None

            await client.write_gatt_char(
                RX_UUID,
                status_command,
                response=False
            )

            print()
            print(
                "Status request inviato."
            )

            print(
                "Attendo risposta: "
                "10 secondi..."
            )

            try:

                await asyncio.wait_for(
                    tester.status_event.wait(),
                    timeout=10
                )

                print()
                print(
                    "STATUS RESPONSE RICEVUTO."
                )

            except asyncio.TimeoutError:

                print()
                print(
                    "NESSUNA STATUS RESPONSE "
                    "entro 10 secondi."
                )

            # =================================================
            # TELEMETRY REQUEST
            # =================================================

            print()
            print("-" * 70)
            print("TELEMETRY REQUEST")
            print("-" * 70)

            telemetry_command = (
                bytes([
                    CMD_SEND_TELEMETRY_REQ,
                    0x00,
                    0x00,
                    0x00,
                ])
                + public_key
            )

            print()
            print(
                "CMD_SEND_TELEMETRY_REQ:"
            )

            print(
                hex_dump(
                    telemetry_command
                )
            )

            tester.telemetry_event = asyncio.Event()
            tester.received_telemetry = None

            await client.write_gatt_char(
                RX_UUID,
                telemetry_command,
                response=False
            )

            print()
            print(
                "Telemetry request inviato."
            )

            print(
                "Attendo telemetria: "
                "30 secondi..."
            )

            try:

                await asyncio.wait_for(
                    tester.telemetry_event.wait(),
                    timeout=30
                )

                print()
                print(
                    "TELEMETRIA RICEVUTA."
                )

            except asyncio.TimeoutError:

                print()
                print(
                    "NESSUNA TELEMETRIA "
                    "entro 30 secondi."
                )

            # =================================================
            # PAUSA TRA I SENSORI
            # =================================================

            await asyncio.sleep(2)

        # ====================================================
        # RIEPILOGO
        # ====================================================

        print()
        print()
        print("=" * 70)
        print("FINE TEST SENSORI")
        print("=" * 70)

        print()
        print(
            "Contatti testati:",
            len(targets)
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("ERRORE")
        print("=" * 70)

        print(
            type(e).__name__,
            ":",
            e
        )

    finally:

        try:

            if client.is_connected:

                await client.stop_notify(
                    TX_UUID
                )

        except Exception:
            pass

        try:

            if client.is_connected:

                await client.disconnect()

        except Exception:
            pass

        print()
        print(
            "Bluetooth disconnesso."
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())