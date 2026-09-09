import asyncio
from meshcore import MeshCore, EventType


MASTER_NAME = "MASTER"


async def main():

    print("=" * 60)
    print("       MESHCORE - TEST MASTER")
    print("=" * 60)

    print()
    print("Ricerca del MASTER via Bluetooth...")

    try:
        # Se l'indirizzo BLE non è specificato,
        # meshcore esegue la ricerca.
        mc = await MeshCore.create_ble(
            None,
            auto_reconnect=True,
            debug=True
        )

    except Exception as e:
        print()
        print("ERRORE DI CONNESSIONE:")
        print(e)
        return

    print()
    print("MASTER CONNESSO")
    print("-" * 60)

    # ---------------------------------------------------------
    # Informazioni del dispositivo
    # ---------------------------------------------------------

    result = await mc.commands.send_device_query()

    if result.type == EventType.ERROR:
        print("Errore DEVICE QUERY:")
        print(result.payload)
    else:
        print("Informazioni MASTER:")
        print(result.payload)

    # ---------------------------------------------------------
    # Informazioni proprie
    # ---------------------------------------------------------

    result = await mc.commands.send_appstart()

    if result.type == EventType.ERROR:
        print("Errore APP START:")
        print(result.payload)
    else:
        print()
        print("SELF INFO:")
        print(result.payload)

    # ---------------------------------------------------------
    # Contatti
    # ---------------------------------------------------------

    print()
    print("Sincronizzazione contatti...")

    result = await mc.commands.get_contacts()

    if result.type == EventType.ERROR:
        print("Errore lettura contatti:")
        print(result.payload)

    else:

        contacts = result.payload

        print()
        print(f"Numero contatti: {len(contacts)}")
        print("-" * 60)

        for key, contact in contacts.items():

            print()
            print("Nome       :", contact.get("adv_name"))
            print("Public Key :", contact.get("public_key"))
            print("Latitudine :", contact.get("adv_lat"))
            print("Longitudine:", contact.get("adv_lon"))
            print("Contatto   :", contact)

    print()
    print("=" * 60)

    await mc.disconnect()


if __name__ == "__main__":
    asyncio.run(main())