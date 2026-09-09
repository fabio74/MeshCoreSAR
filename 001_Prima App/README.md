# MeshCore Tracker — MVP

Applicazione desktop multipiattaforma Windows/macOS per:

- connessione a un Companion MeshCore via USB seriale;
- lettura dei contatti dal dispositivo;
- selezione dei contatti tramite checkbox;
- impostazione `IntPing`;
- richiesta periodica `CMD_SEND_TELEMETRY_REQ (39)`;
- ricezione `PUSH_CODE_TELEMETRY_RESPONSE (0x8B)`;
- decodifica GPS Cayenne LPP `0x88`;
- visualizzazione posizione e traccia su OpenStreetMap;
- visualizzazione offline su GeoTIFF georeferenziato;
- salvataggio CSV separato per contatto.

## 1. Requisiti

Python 3.11 o 3.12 consigliato.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements_minimal.txt
python main.py
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements_minimal.txt
python main.py
```


Per abilitare anche la mappa GeoTIFF offline:

```bash
pip install -r requirements.txt
```

## 2. Collegamento MeshCore

Il firmware deve essere una variante **Companion USB** compatibile con il Companion Protocol.

Baud rate usato dall'MVP: `115200`.

Framing USB:
- app -> radio: `<` + `uint16 little-endian length` + payload;
- radio -> app: `>` + `uint16 little-endian length` + payload.

Sequenza iniziale:
1. `CMD_APP_START`
2. `CMD_DEVICE_QUERY`
3. `CMD_SET_DEVICE_TIME`
4. `CMD_GET_CONTACTS`

## 3. Polling

Selezionare uno o più contatti, impostare `IntPing`, quindi premere **Avvia**.

Le richieste vengono sfalsate all'interno dell'intervallo per evitare un burst contemporaneo sulla rete.

## 4. CSV

I file vengono creati in:

```text
data/
  YYYY-MM-DD/
    YYYY-MM-DD_HH-MM-SS_NomeContatto.csv
```

Una riga viene aggiunta per ogni `0x8B` contenente una posizione GPS valida.

## 5. Mappa online

La mappa online usa Leaflet + tile OpenStreetMap. Richiede accesso Internet.

Per una distribuzione pubblica/ampia va usato un provider di tile conforme alla relativa policy, oppure un proprio tile server.

## 6. GeoTIFF offline

Il file deve contenere un CRS/georeferenziazione. I normali TIFF senza georeferenziazione non consentono di convertire automaticamente GPS -> pixel.

Sono usati `rasterio` e `pyproj`.

## 7. Creazione applicazione Windows/macOS

Installare PyInstaller:

```bash
pip install pyinstaller
```

Build base:

```bash
pyinstaller --noconfirm --windowed --name MeshCoreTracker main.py
```

La cartella risultante sarà sotto `dist/`.

Nota: la build con PySide6 WebEngine e rasterio può richiedere aggiustamenti specifici di piattaforma; prima va verificato l'MVP sul dispositivo MeshCore reale.

## 8. Primo test consigliato

1. Collegare il Companion MeshCore via USB.
2. Avviare il programma.
3. Premere **Aggiorna** e selezionare la porta.
4. Premere **Connetti**.
5. Verificare che i contatti compaiano nella barra laterale.
6. Selezionare `GaucsFig1` / `GaucsFig2` (o i contatti desiderati).
7. Lasciare `IntPing = 15 s`.
8. Premere **Avvia**.
9. Verificare marker, traccia e file CSV.
