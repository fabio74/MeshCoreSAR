import asyncio
from datetime import datetime

from bleak import BleakClient


# ============================================================
# GAUCS
# ============================================================

ADDRESS = "F5:F9:AE:CC:95:2B"

MESHCORE_SERVICE_UUID = (
    "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
)

MESHCORE_RX_UUID = (
    "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
)

MESHCORE_TX_UUID = (
    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
)


# ============================================================
# MESHCORE COMMANDS
# ============================================================

CMD_APP_START = 0x01
CMD_GET_CONTACTS = 0x04

CMD_SEND_STATUS_REQ = 0x1B
CMD_SEND_TELEMETRY_REQ = 0x27


# ============================================================
# RESPONSES
# ============================================================

RESP_CODE_SELF_INFO = 0x05
RESP_CODE_CONTACTS_START = 0x02
RESP_CODE_CONTACT = 0x03
RESP_CODE_END_OF_CONTACTS = 0x04
RESP_CODE_SENT = 0x06

PUSH_CODE_STATUS_RESPONSE = 0x87
PUSH_CODE_TELEMETRY_RESPONSE = 0x8B


# ============================================================
# CONTATTI DA TESTARE
# ============================================================

TARGETS = [
    "GaucsFig1",
    "GaucsFig2",
]


# ============================================================
# APP START
# ============================================================

CMD_APP_START_FRAME = bytes([
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
    return " ".join(f"{b:02X}" for b in data)


def ascii_dump(data):
    return "".join(
        chr(b) if 32 <= b <= 126 else "."
        for b in data
    )


def timestamp():
    return datetime.now().isoformat(
        timespec="milliseconds"
    )


# ============================================================
# CONTATTI
# ============================================================

def decode_contact(frame):

    # frame:
    #
    # 03
    # + 147 byte contact payload

    if len(frame) < 148:
        return None

    payload = frame[1:]

    public_key = payload[0:32]

    name_raw = payload[99:131]

    name = name_raw.split(
        b"\x00",
        1
    )[0].decode(
        "utf-8",
        errors="replace"
    )

    # Dati GPS già verificati con i tuoi frame
    #
    # lat @ 136
    # lon @ 140

    import struct

    latitude_raw = struct.unpack_from(
        "<i",
        frame,
        137
    )[0]

    longitude_raw = struct.unpack_from(
        "<i",
        frame,
        141
    )[0]

    latitude = latitude_raw / 1_000_000
    longitude = longitude_raw / 1_000_000

    return {
        "name": name,
        "public_key": public_key,
        "latitude": latitude,
        "longitude": longitude,
    }


# ============================================================
# TESTER
# ============================================================

class MeshCoreTester:

    def __init__(self):

        self.contacts = {}

        self.contacts_finished = asyncio.Event()

        self.status_event = asyncio.Event()

        self.telemetry_event = asyncio.Event()

        self.last_status = None

        self.last_telemetry = None

    # --------------------------------------------------------
    # NOTIFICATION
    # --------------------------------------------------------

    def notification_handler(
        self,
        sender,
        data
    ):

        data = bytes(data)

        if not data:
            return

        code = data[0]

        print()
        print("=" * 70)
        print("FRAME RICEVUTO")
        print("=" * 70)

        print(
            "Timestamp:",
            timestamp()
        )

        print()
        print("HEX:")
        print(hex_dump(data))

        print()
        print("LEN:", len(data))

        print(
            "CODE:",
            f"0x{code:02X}"
        )

        print()
        print("ASCII:")
        print(ascii_dump(data))

        # ====================================================
        # SELF INFO
        # ====================================================

        if code == RESP_CODE_SELF_INFO:

            print()
            print(">>> RESP_CODE_SELF_INFO")

        # ====================================================
        # CONTACTS START
        # ====================================================

        elif code == RESP_CODE_CONTACTS_START:

            print()
            print(">>> RESP_CODE_CONTACTS_START")

        # ====================================================
        # CONTACT
        # ====================================================

        elif code == RESP_CODE_CONTACT:

            contact = decode_contact(data)

            if contact:

                name = contact["name"]

                self.contacts[name] = contact

                print()
                print(">>> RESP_CODE_CONTACT")

                print()
                print("CONTATTO:")
                print("  Nome      :", name)
                print(
                    "  PublicKey :",
                    contact["public_key"].hex()
                )

                print(
                    "  GPS       :",
                    f"{contact['latitude']:.6f}, "
                    f"{contact['longitude']:.6f}"
                )

        # ====================================================
        # END CONTACTS
        # ====================================================

        elif code == RESP_CODE_END_OF_CONTACTS:

            print()
            print(
                ">>> RESP_CODE_END_OF_CONTACTS"
            )

            self.contacts_finished.set()

        # ====================================================
        # SENT
        # ====================================================

        elif code == RESP_CODE_SENT:

            print()
            print(">>> RESP_CODE_SENT")

        # ====================================================
        # STATUS
        # ====================================================

        elif code == PUSH_CODE_STATUS_RESPONSE:

            print()
            print(
                ">>> PUSH_CODE_STATUS_RESPONSE"
            )

            self.last_status = data

            self.status_event.set()

        # ====================================================
        # TELEMETRY
        # ====================================================

        elif code == PUSH_CODE_TELEMETRY_RESPONSE:

            print()
            print(
                ">>> PUSH_CODE_TELEMETRY_RESPONSE"
            )

            self.last_telemetry = data

            self.telemetry_event.set()

        # ====================================================
        # UNKNOWN
        # ====================================================

        else:

            print()
            print(
                ">>> CODICE NON DECODIFICATO"
            )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("       MESHCORE - SENSOR REQUEST TEST")
    print("=" * 70)

    print()
    print("GAUCS:", ADDRESS)

    client = BleakClient(
        ADDRESS
    )

    tester = MeshCoreTester()

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

            print(
                "ERRORE: impossibile connettersi."
            )

            return

        # ====================================================
        # SERVIZI
        # ====================================================

        print()
        print("=" * 70)
        print("RICERCA GATT MESHCORE")
        print("=" * 70)

        services = client.services

        meshcore_service = None
        rx_char = None
        tx_char = None

        for service in services:

            print()
            print(
                "SERVICE:",
                str(service.uuid)
            )

            for char in service.characteristics:

                print(
                    "  CHARACTERISTIC:",
                    str(char.uuid)
                )

                print(
                    "  PROPERTIES:",
                    char.properties
                )

                uuid = str(
                    char.uuid
                ).lower()

                if uuid == MESHCORE_RX_UUID:

                    rx_char = char

                elif uuid == MESHCORE_TX_UUID:

                    tx_char = char

            if (
                str(service.uuid).lower()
                == MESHCORE_SERVICE_UUID
            ):

                meshcore_service = service

        # ====================================================
        # CHECK
        # ====================================================

        print()
        print("-" * 70)

        print(
            "MeshCore service:",
            "OK"
            if meshcore_service
            else "NON TROVATO"
        )

        print(
            "RX:",
            "OK"
            if rx_char
            else "NON TROVATO"
        )

        print(
            "TX:",
            "OK"
            if tx_char
            else "NON TROVATO"
        )

        if not rx_char or not tx_char:

            print()
            print(
                "ERRORE: caratteristiche MeshCore "
                "non trovate."
            )

            return

        # ====================================================
        # NOTIFY
        # ====================================================

        print()
        print("=" * 70)
        print("ATTIVAZIONE NOTIFY")
        print("=" * 70)

        print(
            "TX UUID:",
            tx_char.uuid
        )

        await client.start_notify(
            tx_char,
            tester.notification_handler
        )

        print(
            "Notify TX: OK"
        )

        await asyncio.sleep(0.5)

        # ====================================================
        # APP START
        # ====================================================

        print()
        print("=" * 70)
        print("1) CMD_APP_START")
        print("=" * 70)

        print()
        print("FRAME:")
        print(
            hex_dump(
                CMD_APP_START_FRAME
            )
        )

        await client.write_gatt_char(
            rx_char,
            CMD_APP_START_FRAME,
            response=False
        )

        print()
        print(
            "CMD_APP_START inviato."
        )

        await asyncio.sleep(2)

        # ====================================================
        # GET CONTACTS
        # ====================================================

        print()
        print("=" * 70)
        print("2) CMD_GET_CONTACTS")
        print("=" * 70)

        await client.write_gatt_char(
            rx_char,
            bytes([CMD_GET_CONTACTS]),
            response=False
        )

        print()
        print(
            "CMD_GET_CONTACTS inviato."
        )

        try:

            await asyncio.wait_for(
                tester.contacts_finished.wait(),
                timeout=15
            )

        except asyncio.TimeoutError:

            print()
            print(
                "TIMEOUT lista contatti."
            )

        # ====================================================
        # RIEPILOGO
        # ====================================================

        print()
        print("=" * 70)
        print("CONTATTI DISPONIBILI")
        print("=" * 70)

        for name, contact in tester.contacts.items():

            print(
                f"{name:25s} "
                f"{contact['latitude']:11.6f} "
                f"{contact['longitude']:11.6f}"
            )

        # ====================================================
        # TEST TARGET
        # ====================================================

        for target_name in TARGETS:

            print()
            print()
            print("#" * 70)
            print(
                f"TEST CONTATTO: {target_name}"
            )
            print("#" * 70)

            contact = tester.contacts.get(
                target_name
            )

            if contact is None:

                print()
                print(
                    "CONTATTO NON TROVATO"
                )

                continue

            public_key = contact[
                "public_key"
            ]

            print()
            print(
                "Public Key:"
            )

            print(
                hex_dump(public_key)
            )

            # =================================================
            # STATUS REQUEST
            # =================================================

            print()
            print("-" * 70)
            print("CMD_SEND_STATUS_REQ")
            print("-" * 70)

            status_frame = (
                bytes([
                    CMD_SEND_STATUS_REQ
                ])
                + public_key
            )

            print()
            print("TX:")
            print(
                hex_dump(status_frame)
            )

            tester.status_event.clear()
            tester.last_status = None

            await client.write_gatt_char(
                rx_char,
                status_frame,
                response=False
            )

            print()
            print(
                "STATUS REQUEST inviato."
            )

            try:

                await asyncio.wait_for(
                    tester.status_event.wait(),
                    timeout=20
                )

                print()
                print(
                    "STATUS RESPONSE RICEVUTO."
                )

            except asyncio.TimeoutError:

                print()
                print(
                    "TIMEOUT STATUS."
                )

            # =================================================
            # TELEMETRY REQUEST
            # =================================================

            print()
            print("-" * 70)
            print("CMD_SEND_TELEMETRY_REQ")
            print("-" * 70)

            telemetry_frame = (
                bytes([
                    CMD_SEND_TELEMETRY_REQ,
                    0x00,
                    0x00,
                    0x00
                ])
                + public_key
            )

            print()
            print("TX:")
            print(
                hex_dump(
                    telemetry_frame
                )
            )

            tester.telemetry_event.clear()
            tester.last_telemetry = None

            await client.write_gatt_char(
                rx_char,
                telemetry_frame,
                response=False
            )

            print()
            print(
                "TELEMETRY REQUEST inviato."
            )

            print(
                "Attesa risposta: 30 secondi..."
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
                    "TIMEOUT TELEMETRIA."
                )

            await asyncio.sleep(2)

        # ====================================================
        # END
        # ====================================================

        print()
        print()
        print("=" * 70)
        print("TEST TERMINATO")
        print("=" * 70)

    except Exception as e:

        print()
        print("=" * 70)
        print("ERRORE")
        print("=" * 70)

        print(
            type(e).__name__,
            ":",
            str(e)
        )

    finally:

        try:

            if client.is_connected:

                await client.stop_notify(
                    tx_char
                    if tx_char
                    else MESHCORE_TX_UUID
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