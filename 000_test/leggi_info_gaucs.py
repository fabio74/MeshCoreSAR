import asyncio
from bleak import BleakClient


ADDRESS = "F5:F9:AE:CC:95:2B"

DEVICE_INFO_SERVICE = "0000180A-0000-1000-8000-00805F9B34FB"

CHARACTERISTICS = {
    "Model Number": "00002A24-0000-1000-8000-00805F9B34FB",
    "Serial Number": "00002A25-0000-1000-8000-00805F9B34FB",
    "Firmware Revision": "00002A26-0000-1000-8000-00805F9B34FB",
    "Hardware Revision": "00002A27-0000-1000-8000-00805F9B34FB",
    "Software Revision": "00002A28-0000-1000-8000-00805F9B34FB",
    "Manufacturer": "00002A29-0000-1000-8000-00805F9B34FB",
}


async def main():

    print("=" * 70)
    print("             INFORMAZIONI GAUCS")
    print("=" * 70)

    async with BleakClient(ADDRESS) as client:

        print("\nConnesso:", client.is_connected)

        print("\nInformazioni dispositivo:")
        print("-" * 70)

        for name, uuid in CHARACTERISTICS.items():

            try:

                data = await client.read_gatt_char(uuid)

                try:
                    value = data.decode("utf-8").rstrip("\x00")

                except UnicodeDecodeError:
                    value = data.hex(" ")

                print(f"{name:20}: {value}")

            except Exception as e:

                print(f"{name:20}: ERRORE - {e}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())