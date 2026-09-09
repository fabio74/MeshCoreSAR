import asyncio
import struct
from datetime import datetime

from bleak import BleakClient


# ============================================================
# CONFIGURAZIONE
# ============================================================

ADDRESS = "F5:F9:AE:CC:95:2B"

RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


# ============================================================
# MESHCORE COMPANION PROTOCOL
# ============================================================

CMD_APP_START = 0x01
CMD_GET_CONTACTS = 0x04

RESP_CODE_SELF_INFO = 0x05
RESP_CODE_CONTACTS_START = 0x02
RESP_CODE_CONTACT = 0x03
RESP_CODE_END_OF_CONTACTS = 0x04


# ------------------------------------------------------------
# CMD_APP_START
#
# 01 03 00 00 00 00 00 00 "mccli"
# ------------------------------------------------------------

APP_START = (
    bytes([
        CMD_APP_START,
        0x03,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ])
    + b"mccli"
)


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


def u16_le(data, offset):

    if len(data) < offset + 2:
        return None

    return struct.unpack_from("<H", data, offset)[0]


def u32_le(data, offset):

    if len(data) < offset + 4:
        return None

    return struct.unpack_from("<I", data, offset)[0]


def i32_le(data, offset):

    if len(data) < offset + 4:
        return None

    return struct.unpack_from("<i", data, offset)[0]


# ============================================================
# DECODIFICA SELF INFO
# ============================================================

def decode_self_info(data):

    print()
    print("------------------------------------------------------------")
    print("RESP_CODE_SELF_INFO")
    print("------------------------------------------------------------")

    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    if len(data) < 1:
        return

    print("CODE:", f"0x{data[0]:02X}")

    if len(data) > 1:
        print("Payload HEX:")
        print(hex_dump(data[1:]))

    print()
    print("ASCII:")
    print(ascii_dump(data))


# ============================================================
# DECODIFICA CONTACTS START
# ============================================================

def decode_contacts_start(data):

    print()
    print("------------------------------------------------------------")
    print("RESP_CODE_CONTACTS_START")
    print("------------------------------------------------------------")

    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    print("CODE:", f"0x{data[0]:02X}")

    if len(data) > 1:

        payload = data[1:]

        print()
        print("PAYLOAD HEX:")
        print(hex_dump(payload))

        print()
        print("PAYLOAD ASCII:")
        print(ascii_dump(payload))


# ============================================================
# DECODIFICA CONTACT
# ============================================================

def decode_contact(data, contact_number):

    print()
    print("------------------------------------------------------------")
    print(f"RESP_CODE_CONTACT  #{contact_number}")
    print("------------------------------------------------------------")

    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    print("CODE:", f"0x{data[0]:02X}")

    payload = data[1:]

    print()
    print("PAYLOAD HEX:")
    print(hex_dump(payload))

    print()
    print("PAYLOAD ASCII:")
    print(ascii_dump(payload))

    # --------------------------------------------------------
    # Proviamo a estrarre campi utili senza fare assunzioni
    # sul formato completo.
    # --------------------------------------------------------

    if len(payload) >= 4:

        print()
        print("Possibili campi numerici:")

        value_u32 = u32_le(payload, 0)

        if value_u32 is not None:
            print(
                "  uint32 LE @0 :",
                value_u32,
                f"(0x{value_u32:08X})"
            )

    # --------------------------------------------------------
    # Ricerca di stringhe ASCII leggibili
    # --------------------------------------------------------

    ascii_sequences = []

    current = bytearray()

    for byte in payload:

        if 32 <= byte <= 126:

            current.append(byte)

        else:

            if len(current) >= 3:

                ascii_sequences.append(
                    current.decode(
                        "ascii",
                        errors="replace"
                    )
                )

            current = bytearray()

    if len(current) >= 3:

        ascii_sequences.append(
            current.decode(
                "ascii",
                errors="replace"
            )
        )

    if ascii_sequences:

        print()
        print("Stringhe ASCII trovate:")

        for text in ascii_sequences:

            print(" ", repr(text))


# ============================================================
# DECODIFICA END CONTACTS
# ============================================================

def decode_end_contacts(data):

    print()
    print("------------------------------------------------------------")
    print("RESP_CODE_END_OF_CONTACTS")
    print("------------------------------------------------------------")

    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    print("CODE:", f"0x{data[0]:02X}")

    if len(data) > 1:

        print()
        print("PAYLOAD HEX:")
        print(hex_dump(data[1:]))


# ============================================================
# DECODIFICATORE GENERALE
# ============================================================

def decode_packet(data, contact_counter):

    if not data:

        print("\nFRAME VUOTO")
        return contact_counter, False

    code = data[0]

    print()
    print("=" * 70)
    print("FRAME RICEVUTO")
    print("=" * 70)

    print("Timestamp:", datetime.now().isoformat(
        timespec="milliseconds"
    ))

    print()
    print("HEX:")
    print(hex_dump(data))

    print()
    print("LEN:", len(data))

    print(
        "CODE:",
        f"0x{code:02X}"
    )

    # --------------------------------------------------------
    # SELF INFO
    # --------------------------------------------------------

    if code == RESP_CODE_SELF_INFO:

        decode_self_info(data)

    # --------------------------------------------------------
    # CONTACTS START
    # --------------------------------------------------------

    elif code == RESP_CODE_CONTACTS_START:

        decode_contacts_start(data)

    # --------------------------------------------------------
    # CONTACT
    # --------------------------------------------------------

    elif code == RESP_CODE_CONTACT:

        contact_counter += 1

        decode_contact(
            data,
            contact_counter
        )

    # --------------------------------------------------------
    # END CONTACTS
    # --------------------------------------------------------

    elif code == RESP_CODE_END_OF_CONTACTS:

        decode_end_contacts(data)

        return contact_counter, True

    # --------------------------------------------------------
    # ALTRO
    # --------------------------------------------------------

    else:

        print()
        print("CODICE NON GESTITO")
        print(
            "Payload HEX:",
            hex_dump(data[1:])
        )

        print(
            "Payload ASCII:",
            ascii_dump(data[1:])
        )

    return contact_counter, False


# ============================================================
# PROGRAMMA PRINCIPALE
# ============================================================

async def main():

    print("=" * 70)
    print("       MESHCORE - GET CONTACTS TEST")
    print("=" * 70)

    print()
    print("GAUCS :", ADDRESS)
    print("RX    :", RX_UUID)
    print("TX    :", TX_UUID)

    client = BleakClient(ADDRESS)

    contact_counter = 0
    contacts_finished = asyncio.Event()

    # --------------------------------------------------------
    # CALLBACK BLE
    # --------------------------------------------------------

    def notification_handler(sender, data):

        nonlocal contact_counter

        data = bytes(data)

        contact_counter, finished = decode_packet(
            data,
            contact_counter
        )

        if finished:

            contacts_finished.set()

    try:

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        print()
        print("Connessione BLE...")

        await client.connect()

        print(
            "Connesso:",
            client.is_connected
        )

        if not client.is_connected:

            print("ERRORE: connessione fallita.")
            return

        # ----------------------------------------------------
        # NOTIFY
        # ----------------------------------------------------

        print()
        print("Attivazione notifiche TX...")

        await client.start_notify(
            TX_UUID,
            notification_handler
        )

        print("Notify TX: OK")

        # ----------------------------------------------------
        # APP START
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("1) CMD_APP_START")
        print("=" * 70)

        print()
        print("Invio:")
        print(hex_dump(APP_START))

        await client.write_gatt_char(
            RX_UUID,
            APP_START,
            response=False
        )

        print()
        print("CMD_APP_START inviato.")

        # ----------------------------------------------------
        # SELF INFO
        # ----------------------------------------------------

        print()
        print("Attendo RESP_CODE_SELF_INFO...")

        await asyncio.sleep(1)

        # ----------------------------------------------------
        # GET CONTACTS
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("2) CMD_GET_CONTACTS")
        print("=" * 70)

        CMD = bytes([
            CMD_GET_CONTACTS
        ])

        print()
        print("Invio:")
        print(hex_dump(CMD))

        contact_counter = 0
        contacts_finished.clear()

        await client.write_gatt_char(
            RX_UUID,
            CMD,
            response=False
        )

        print()
        print("CMD_GET_CONTACTS inviato.")

        # ----------------------------------------------------
        # WAIT CONTACTS
        # ----------------------------------------------------

        print()
        print("Attendo la lista dei contatti...")
        print("Timeout: 30 secondi")

        try:

            await asyncio.wait_for(
                contacts_finished.wait(),
                timeout=30
            )

            print()
            print("=" * 70)
            print("FINE LISTA CONTATTI")
            print("=" * 70)

            print()
            print(
                "Numero di frame CONTACT ricevuti:",
                contact_counter
            )

        except asyncio.TimeoutError:

            print()
            print("=" * 70)
            print("TIMEOUT")
            print("=" * 70)

            print()
            print(
                "Non è arrivato RESP_CODE_END_OF_CONTACTS "
                "entro 30 secondi."
            )

            print(
                "Frame CONTACT ricevuti:",
                contact_counter
            )

        # ----------------------------------------------------
        # CLEANUP
        # ----------------------------------------------------

        await client.stop_notify(TX_UUID)

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

        if client.is_connected:

            await client.disconnect()

        print()
        print("=" * 70)
        print("Bluetooth disconnesso")
        print("=" * 70)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())