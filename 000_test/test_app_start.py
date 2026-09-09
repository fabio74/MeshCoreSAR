import asyncio
from bleak import BleakClient


ADDRESS = "F5:F9:AE:CC:95:2B"

RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


# MeshCore Companion Protocol
#
# CMD_APP_START
#
# byte 0     = 0x01
# byte 1     = app version
# bytes 2-7  = reserved
# bytes 8... = application name
#
# Usiamo protocol version 3 e "mccli".
APP_START = bytes([
    0x01,
    0x03,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
]) + b"mccli"


async def main():

    print("=" * 70)
    print("       MESHCORE CMD_APP_START TEST")
    print("=" * 70)

    print()
    print("GAUCS :", ADDRESS)
    print("RX    :", RX_UUID)
    print("TX    :", TX_UUID)

    client = BleakClient(ADDRESS)

    try:

        # --------------------------------------------------
        # CONNECT
        # --------------------------------------------------

        print("\nConnessione BLE...")

        await client.connect()

        print("Connesso:", client.is_connected)

        # --------------------------------------------------
        # PAIR
        # --------------------------------------------------

        print("\nTentativo pairing BLE...")

        try:

            paired = await client.pair()

            print("Pairing risultato:", paired)

        except Exception as e:

            print("Pairing non eseguito:")
            print(type(e).__name__, e)

            print(
                "\nContinuo comunque: il dispositivo potrebbe "
                "essere già autenticato."
            )

        # --------------------------------------------------
        # SERVICES
        # --------------------------------------------------

        print("\nVerifica caratteristiche MeshCore...")

        services = client.services

        rx_found = False
        tx_found = False

        for service in services:

            for char in service.characteristics:

                if char.uuid.lower() == RX_UUID.lower():
                    rx_found = True

                if char.uuid.lower() == TX_UUID.lower():
                    tx_found = True

        print("RX:", "OK" if rx_found else "NON TROVATO")
        print("TX:", "OK" if tx_found else "NON TROVATO")

        if not rx_found or not tx_found:

            print("\nERRORE: caratteristiche MeshCore mancanti.")
            return

        # --------------------------------------------------
        # NOTIFICATION
        # --------------------------------------------------

        response_event = asyncio.Event()
        received_packets = []

        def notification_handler(sender, data):

            data = bytes(data)

            print()
            print("<<< RISPOSTA BLE")

            print("HEX:")
            print(data.hex(" "))

            print("LEN:", len(data))

            if len(data) > 0:

                print(
                    "PACKET CODE:",
                    f"0x{data[0]:02X}"
                )

                if data[0] == 0x05:

                    print()
                    print("!!! RESP_CODE_SELF_INFO RICEVUTO !!!")

                    print(
                        "CMD_APP_START eseguito correttamente."
                    )

            received_packets.append(data)

            response_event.set()

        print("\nAttivazione notifiche TX...")

        try:

            await client.start_notify(
                TX_UUID,
                notification_handler
            )

            print("Notify TX: OK")

        except Exception as e:

            print()
            print("ERRORE ATTIVANDO TX NOTIFY:")
            print(type(e).__name__)
            print(e)

            print()
            print(
                "Il problema è l'autenticazione BLE, "
                "non il protocollo MeshCore."
            )

            return

        # --------------------------------------------------
        # SEND CMD_APP_START
        # --------------------------------------------------

        print("\n" + "=" * 70)
        print("INVIO CMD_APP_START")
        print("=" * 70)

        print()
        print("Frame HEX:")
        print(APP_START.hex(" "))

        print()
        print("Scrittura su RX...")

        await client.write_gatt_char(
            RX_UUID,
            APP_START,
            response=False
        )

        print("CMD_APP_START inviato.")

        # --------------------------------------------------
        # WAIT RESPONSE
        # --------------------------------------------------

        print()
        print("Attendo RESP_CODE_SELF_INFO...")
        print("Timeout: 10 secondi")

        try:

            await asyncio.wait_for(
                response_event.wait(),
                timeout=10
            )

        except asyncio.TimeoutError:

            print()
            print("TIMEOUT")

            print(
                "Nessuna risposta dal GAUCS."
            )

            return

        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        print()
        print("=" * 70)
        print("RISULTATO")
        print("=" * 70)

        for packet in received_packets:

            print()
            print("Packet:", packet.hex(" "))

            if packet:

                if packet[0] == 0x05:

                    print()
                    print("SUCCESSO")
                    print(
                        "GAUCS ha risposto a CMD_APP_START "
                        "con RESP_CODE_SELF_INFO."
                    )

                elif packet[0] == 0x01:

                    print("RESP_CODE_ERR / risposta inattesa")

                else:

                    print(
                        "Packet code:",
                        f"0x{packet[0]:02X}"
                    )

        # --------------------------------------------------
        # CLEANUP
        # --------------------------------------------------

        try:
            await client.stop_notify(TX_UUID)
        except Exception:
            pass

    except Exception as e:

        print()
        print("=" * 70)
        print("ERRORE")
        print("=" * 70)

        print(type(e).__name__)
        print(e)

    finally:

        if client.is_connected:

            await client.disconnect()

        print()
        print("Bluetooth disconnesso.")


if __name__ == "__main__":

    asyncio.run(main())