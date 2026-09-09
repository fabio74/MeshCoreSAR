import asyncio
from bleak import BleakScanner, BleakClient


DEVICE_NAME = "MeshCore-GAUCS"
DEVICE_ADDRESS = "F5:F9:AE:CC:95:2B"


MESHCORE_SERVICE = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
MESHCORE_RX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
MESHCORE_TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


async def main():

    print("=" * 70)
    print("          DIAGNOSTICA BLE MESHCORE")
    print("=" * 70)

    # ---------------------------------------------------------
    # SCANSIONE
    # ---------------------------------------------------------

    print("\nRicerca dispositivi MeshCore...\n")

    devices = await BleakScanner.discover(timeout=10)

    target = None

    for device in devices:

        print(
            f"Nome: {device.name!r:30} "
            f"Address: {device.address}"
        )

        if (
            device.address.upper() == DEVICE_ADDRESS.upper()
            or device.name == DEVICE_NAME
        ):
            target = device

    if target is None:

        print("\nERRORE: dispositivo GAUCS non trovato.")
        return

    # ---------------------------------------------------------
    # DISPOSITIVO
    # ---------------------------------------------------------

    print("\n" + "-" * 70)
    print("DISPOSITIVO TROVATO")
    print("-" * 70)

    print("Nome    :", target.name)
    print("Address :", target.address)

    # ---------------------------------------------------------
    # CONNESSIONE
    # ---------------------------------------------------------

    print("\nConnessione...")

    try:

        async with BleakClient(target) as client:

            print("Connesso:", client.is_connected)

            # -------------------------------------------------
            # SERVIZI
            # -------------------------------------------------

            print("\n" + "=" * 70)
            print("SERVIZI GATT")
            print("=" * 70)

            services = client.services

            for service in services:

                print()
                print("SERVICE")
                print(" UUID:", service.uuid)

                for characteristic in service.characteristics:

                    print()
                    print("   CHARACTERISTIC")
                    print("   UUID :", characteristic.uuid)
                    print("   Flags:", characteristic.properties)

                    for descriptor in characteristic.descriptors:

                        print(
                            "      DESCRIPTOR:",
                            descriptor.uuid
                        )

            # -------------------------------------------------
            # RICERCA MESHCORE
            # -------------------------------------------------

            print("\n" + "=" * 70)
            print("RICERCA UUID MESHCORE")
            print("=" * 70)

            service_found = False
            rx_found = False
            tx_found = False

            for service in services:

                if service.uuid.lower() == MESHCORE_SERVICE.lower():

                    service_found = True

                for characteristic in service.characteristics:

                    uuid = characteristic.uuid.lower()

                    if uuid == MESHCORE_RX.lower():

                        rx_found = True

                    if uuid == MESHCORE_TX.lower():

                        tx_found = True

            print(
                "SERVICE :",
                "OK" if service_found else "NON TROVATO"
            )

            print(
                "RX      :",
                "OK" if rx_found else "NON TROVATO"
            )

            print(
                "TX      :",
                "OK" if tx_found else "NON TROVATO"
            )

            # -------------------------------------------------
            # RIEPILOGO
            # -------------------------------------------------

            print("\n" + "=" * 70)
            print("RIEPILOGO")
            print("=" * 70)

            if service_found and rx_found and tx_found:

                print("""
Il servizio Companion MeshCore è presente.

SERVICE : OK
RX      : OK
TX      : OK

Il collegamento BLE è compatibile con il protocollo
Companion MeshCore.
""")

            else:

                print("""
ATTENZIONE

Il dispositivo si connette via Bluetooth, ma il servizio
Companion MeshCore atteso non è stato trovato completamente.
""")

            print("=" * 70)

    except Exception as e:

        print("\nERRORE DURANTE LA CONNESSIONE:")
        print(type(e).__name__)
        print(e)


if __name__ == "__main__":

    asyncio.run(main())