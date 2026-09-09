import asyncio
from bleak import BleakClient


ADDRESS = "F5:F9:AE:CC:95:2B"


async def main():

    print("=" * 70)
    print("       TEST BLE GAUCS - MESHCORE")
    print("=" * 70)

    async with BleakClient(ADDRESS) as client:

        print("\nConnesso:", client.is_connected)

        print("\nSERVIZI DISPONIBILI")
        print("-" * 70)

        for service in client.services:

            print(f"\nSERVICE: {service.uuid}")

            for char in service.characteristics:

                print(f"  CHARACTERISTIC: {char.uuid}")
                print(f"  PROPERTIES:     {char.properties}")

                if "read" in char.properties:

                    try:
                        data = await client.read_gatt_char(char.uuid)

                        print(
                            "  READ:",
                            data.hex(" ")
                        )

                        try:
                            print(
                                "  TEXT:",
                                data.decode(
                                    "utf-8",
                                    errors="replace"
                                )
                            )
                        except Exception:
                            pass

                    except Exception as e:

                        print(
                            "  READ ERROR:",
                            e
                        )

        print("\n" + "=" * 70)
        print("TEST NOTIFY")
        print("=" * 70)

        # Proviamo ad attivare le notifiche su tutte le
        # caratteristiche che le supportano.

        notify_chars = []

        for service in client.services:

            for char in service.characteristics:

                if "notify" in char.properties:

                    notify_chars.append(char.uuid)

        print(
            "\nCaratteristiche NOTIFY:",
            len(notify_chars)
        )

        for uuid in notify_chars:

            print("\nNotify:", uuid)

            async def callback(sender, data, uuid=uuid):

                print(
                    f"\n[NOTIFY {uuid}]",
                    data.hex(" ")
                )

            try:

                await client.start_notify(
                    uuid,
                    callback
                )

                print("  OK")

            except Exception as e:

                print("  ERRORE:", e)

        print("\nIn ascolto per 15 secondi...")
        print("Se il telefono/app MeshCore genera traffico")
        print("potremmo vedere i frame BLE.")

        await asyncio.sleep(15)

        for uuid in notify_chars:

            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

    print("\nConnessione chiusa.")


if __name__ == "__main__":
    asyncio.run(main())