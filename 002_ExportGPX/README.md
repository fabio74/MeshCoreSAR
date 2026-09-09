# MeshCore Tracker — MVP v2

Applicazione desktop multipiattaforma Windows/macOS per acquisire e visualizzare le posizioni dei contatti MeshCore tramite Companion USB.

## Funzioni

- connessione MeshCore Companion via USB seriale;
- lettura automatica dei contatti;
- checkbox indipendenti per scegliere i contatti da interrogare;
- `IntPing` configurabile;
- polling `CMD_SEND_TELEMETRY_REQ (39)`;
- ricezione `PUSH_CODE_TELEMETRY_RESPONSE (0x8B)`;
- decodifica GPS Cayenne LPP `0x88`;
- CSV separato per contatto;
- esportazione delle tracce registrate in **GPX 1.1**;
- lista separata **Tracce visibili sulla mappa**, per mostrare/nascondere ogni singolo dispositivo senza interrompere il polling;
- barra di stato inferiore con le ultime coordinate di tutti i dispositivi che hanno trasmesso una posizione;
- mappe online selezionabili:
  - OpenStreetMap;
  - OpenTopoMap;
  - Esri World Imagery / Satellite;
- mappa offline GeoTIFF georeferenziata;
- zoom GeoTIFF con rotella mouse, pulsanti `+` / `−`, pulsante **Adatta** e trascinamento per il pan.

## Installazione Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Per usare soltanto USB + GUI + mappe online, senza GeoTIFF:

```powershell
pip install -r requirements_minimal.txt
python main.py
```

## Installazione macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Uso

1. Collegare il dispositivo MeshCore Companion USB.
2. Selezionare la porta e premere **Connetti**.
3. Selezionare nella lista **Contatti da interrogare** i nodi da cui richiedere telemetria.
4. Impostare `IntPing` e premere **Avvia**.
5. Nella lista **Tracce visibili sulla mappa** attivare o disattivare liberamente ogni traccia.
6. Selezionare la cartografia online desiderata oppure passare a GeoTIFF offline.
7. Premere **Esporta tracce GPX…** per creare un unico file GPX contenente una `<trk>` separata per ciascun dispositivo registrato.

## GPX

Il file GPX contiene per ogni punto:

- latitudine;
- longitudine;
- quota, se disponibile;
- timestamp UTC.

Ogni dispositivo è esportato come traccia GPX distinta.

## GeoTIFF offline

Il TIFF deve contenere georeferenziazione e CRS. Un TIFF semplice privo di coordinate geografiche non può essere sovrapposto automaticamente alle coordinate GPS.

Controlli:

- rotella mouse: zoom avanti/indietro;
- trascinamento con mouse: pan;
- `+`: zoom avanti;
- `−`: zoom indietro;
- **Adatta**: visualizza l'intera carta.

## Dati registrati

I CSV vengono salvati in:

```text
data/
  YYYY-MM-DD/
    YYYY-MM-DD_HH-MM-SS_NomeContatto.csv
```

Le tracce restano in memoria per tutta l'esecuzione dell'app e possono essere esportate in GPX in qualsiasi momento.

## Correzione polling v2.1

Le richieste telemetriche ai contatti selezionati sono ora serializzate: l'app attende
`RESP_CODE_SENT (0x06)` e usa il `suggested_timeout` restituito dal radio prima di
passare al contatto successivo. In caso di `RESP_CODE_ERR` o timeout viene eseguito
un retry. Questo evita che un contatto intermedio venga saltato quando il Companion
MeshCore è ancora impegnato con la richiesta precedente.

`IntPing` è ora l'intervallo minimo fra l'inizio di due cicli: se un ciclo richiede più
tempo, il successivo non viene sovrapposto.
