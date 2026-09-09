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


# ============================================================
# STRUTTURA RESP_CODE_CONTACT
#
# Byte:
#
#  0       response code
#  1-32    public key
#  33      type
#  34      flags
#  35      path length
#  36-99   path
#  100-131 name
#  132-135 last advert
#  136-139 latitude
#  140-143 longitude
#  144-147 lastmod
#
# Totale: 148 byte
# ============================================================

CONTACT_LENGTH = 148


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
# FUNZIONI DI DECODIFICA
# ============================================================

def read_u32_le(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def read_i32_le(data, offset):
    return struct.unpack_from("<i", data, offset)[0]


def decode_string(data):
    """
    Decodifica una stringa ASCII/UTF-8 terminata o riempita con 0x00.
    """
    data = data.split(b"\x00", 1)[0]

    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return repr(data)


def decode_contact(data, number):

    if len(data) != CONTACT_LENGTH:

        print()
        print("ATTENZIONE: lunghezza CONTACT inattesa")
        print("Ricevuti:", len(data))
        print("Attesi  :", CONTACT_LENGTH)

        return None

    if data[0] != RESP_CODE_CONTACT:

        print("ERRORE: non è un RESP_CODE_CONTACT")
        return None

    # --------------------------------------------------------
    # Campi
    # --------------------------------------------------------

    public_key = data[1:33]

    contact_type = data[33]

    flags = data[34]

    path_len_raw = data[35]

    path_data = data[36:100]

    name_data = data[100:132]

    last_advert = read_u32_le(data, 132)

    latitude_raw = read_i32_le(data, 136)

    longitude_raw = read_i32_le(data, 140)

    lastmod = read_u32_le(data, 144)

    # --------------------------------------------------------
    # GPS
    #
    # MeshCore usa coordinate in microgradi.
    # --------------------------------------------------------

    latitude = latitude_raw / 1_000_000.0

    longitude = longitude_raw / 1_000_000.0

    # --------------------------------------------------------
    # Path
    # --------------------------------------------------------

    if path_len_raw == 0xFF:

        path_length = -1
        path = ""

    else:

        path_length = path_len_raw

        path = path_data[:path_length].hex(" ")

    # --------------------------------------------------------
    # Nome
    # --------------------------------------------------------

    name = decode_string(name_data)

    # --------------------------------------------------------
    # Stampa
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(f"CONTACT #{number}")
    print("=" * 70)

    print()
    print("Nome:")
    print(f"  {name}")

    print()
    print("Public Key:")
    print(f"  {public_key.hex()}")

    print()
    print("Type:")
    print(f"  0x{contact_type:02X} ({contact_type})")

    print()
    print("Flags:")
    print(f"  0x{flags:02X} ({flags})")

    print()
    print("Path length:")
    print(f"  {path_length}")

    print()
    print("Path:")

    if path:
        print(f"  {path}")
    else:
        print("  <empty>")

    print()
    print("Last Advert:")
    print(f"  {last_advert}")
    print(f"  0x{last_advert:08X}")

    print()
    print("GPS:")
    print(f"  Latitude : {latitude:.6f}")
    print(f"  Longitude: {longitude:.6f}")

    print()
    print("Lastmod:")
    print(f"  {lastmod}")
    print(f"  0x{lastmod:08X}")

    # --------------------------------------------------------
    # Validazione GPS
    # --------------------------------------------------------

    gps_valid = (
        -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
        and not (
            latitude == 0.0
            and longitude == 0.0
        )
    )

    print()
    print("GPS valid:")
    print(f"  {'SI' if gps_valid else 'NO / ASSENTE'}")

    return {
        "number": number,
        "name": name,
        "public_key": public_key.hex(),
        "type": contact_type,
        "flags": flags,
        "path_length": path_length,
        "path": path,
        "last_advert": last_advert,
        "latitude": latitude,
        "longitude": longitude,
        "lastmod": lastmod,
    }


# ============================================================
# CALLBACK BLE
# ============================================================

class ContactCollector:

    def __init__(self):

        self.contacts = []

        self.finished = asyncio.Event()

    def notification_handler(self, sender, data):

        data = bytes(data)

        if not data:
            return

        code = data[0]

        # ----------------------------------------------------
        # SELF INFO
        # ----------------------------------------------------

        if code == RESP_CODE_SELF_INFO:

            print()
            print("-" * 70)
            print("RESP_CODE_SELF_INFO ricevuto")
            print("-" * 70)

            print("HEX:")
            print(data.hex(" "))

        # ----------------------------------------------------
        # CONTACTS START
        # ----------------------------------------------------

        elif code == RESP_CODE_CONTACTS_START:

            print()
            print("=" * 70)
            print("RESP_CODE_CONTACTS_START")
            print("=" * 70)

            print()
            print("HEX:")
            print(data.hex(" "))

            if len(data) >= 5:

                count = struct.unpack_from(
                    "<I",
                    data,
                    1
                )[0]

                print()
                print("Numero contatti dichiarato:")
                print(f"  {count}")

        # ----------------------------------------------------
        # CONTACT
        # ----------------------------------------------------

        elif code == RESP_CODE_CONTACT:

            number = len(self.contacts) + 1

            contact = decode_contact(
                data,
                number
            )

            if contact is not None:

                self.contacts.append(contact)

        # ----------------------------------------------------
        # END
        # ----------------------------------------------------

        elif code == RESP_CODE_END_OF_CONTACTS:

            print()
            print("=" * 70)
            print("RESP_CODE_END_OF_CONTACTS")
            print("=" * 70)

            print()
            print("HEX:")
            print(data.hex(" "))

            self.finished.set()

        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        else:

            print()
            print("FRAME NON RICONOSCIUTO")
            print("HEX:")
            print(data.hex(" "))


# ============================================================
# RIEPILOGO
# ============================================================

def print_summary(contacts):

    print()
    print()
    print("=" * 70)
    print("RIEPILOGO CONTATTI")
    print("=" * 70)

    print()

    if not contacts:

        print("Nessun contatto ricevuto.")
        return

    for contact in contacts:

        print(
            f"{contact['number']:2d} | "
            f"{contact['name']:<25} | "
            f"{contact['latitude']:>11.6f} | "
            f"{contact['longitude']:>11.6f}"
        )

    print()
    print("-" * 70)
    print(
        f"Totale contatti ricevuti: {len(contacts)}"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 70)
    print("       MESHCORE - DECODE CONTACTS")
    print("=" * 70)

    print()
    print("GAUCS :", ADDRESS)
    print("RX    :", RX_UUID)
    print("TX    :", TX_UUID)

    client = BleakClient(ADDRESS)

    collector = ContactCollector()

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

            print("ERRORE: impossibile connettersi.")
            return

        # ----------------------------------------------------
        # NOTIFY
        # ----------------------------------------------------

        print()
        print("Attivazione notifiche...")

        await client.start_notify(
            TX_UUID,
            collector.notification_handler
        )

        print("Notify TX: OK")

        # ----------------------------------------------------
        # APP START
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("CMD_APP_START")
        print("=" * 70)

        print()
        print("HEX:")
        print(APP_START.hex(" "))

        await client.write_gatt_char(
            RX_UUID,
            APP_START,
            response=False
        )

        print()
        print("CMD_APP_START inviato.")

        # Attesa SELF_INFO
        await asyncio.sleep(1)

        # ----------------------------------------------------
        # GET CONTACTS
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("CMD_GET_CONTACTS")
        print("=" * 70)

        command = bytes([
            CMD_GET_CONTACTS
        ])

        print()
        print("HEX:")
        print(command.hex(" "))

        await client.write_gatt_char(
            RX_UUID,
            command,
            response=False
        )

        print()
        print("CMD_GET_CONTACTS inviato.")

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        print()
        print("Attesa lista contatti...")
        print("Timeout: 30 secondi")

        try:

            await asyncio.wait_for(
                collector.finished.wait(),
                timeout=30
            )

        except asyncio.TimeoutError:

            print()
            print("=" * 70)
            print("TIMEOUT")
            print("=" * 70)

            print(
                "Non è stato ricevuto "
                "RESP_CODE_END_OF_CONTACTS."
            )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        print_summary(
            collector.contacts
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
        print("=" * 70)
        print("Bluetooth disconnesso")
        print("=" * 70)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())