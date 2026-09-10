# MeshCore Tracker MAUI 1.0

Prima conversione dell'MVP Python v2.1 in C# / .NET MAUI per Visual Studio.

## Funzioni incluse

- Windows + macOS (Mac Catalyst) nello stesso progetto MAUI.
- USB seriale a 115200 baud tramite `System.IO.Ports`.
- framing USB MeshCore `<` / `>` con lunghezza uint16 little-endian.
- `CMD_APP_START`, `CMD_DEVICE_QUERY`, sincronizzazione ora e `CMD_GET_CONTACTS`.
- elenco contatti con checkbox.
- polling sequenziale dei contatti selezionati.
- rispetto del `suggested_timeout` di `RESP_CODE_SENT (0x06)`.
- un retry in caso di errore/timeout.
- decodifica `0x8B` + Cayenne LPP GPS `0x88` e sensori già gestiti dalla versione Python.
- CSV separato per contatto.
- GPX 1.1 con una traccia per dispositivo.
- mappa Leaflet con OpenStreetMap, OpenTopoMap, Esri Satellite.
- visibilità indipendente di ogni traccia.
- coordinate più recenti di tutti i dispositivi nella barra bassa.
- GeoTIFF offline con zoom/pan tramite Leaflet.
- script inclusi per incorporare localmente Leaflet, Proj4js e geotiff.js prima della build destinata all'uso offline.

## GeoTIFF MVP

Il loader offline legge il raster direttamente nel WebView tramite geotiff.js e supporta inizialmente:

- EPSG:4326
- EPSG:3857
- WGS84 / UTM nord EPSG:32601..32660
- WGS84 / UTM sud EPSG:32701..32760

I raster grandi vengono ridimensionati a massimo 2500 px sul lato maggiore per la visualizzazione. Le tracce originali non vengono modificate.

## Requisiti Windows

- Windows 10 1809+ / Windows 11
- Visual Studio 2022 con workload **.NET Multi-platform App UI development**
- .NET 10 SDK / MAUI workload

Aprire `MeshCoreTracker.sln`, scegliere target **Windows Machine** e avviare.

Da terminale, dopo aver installato il workload MAUI:

```powershell
dotnet workload install maui
dotnet restore MeshCoreTracker\MeshCoreTracker.csproj
dotnet build MeshCoreTracker\MeshCoreTracker.csproj -f net10.0-windows10.0.19041.0
```

### Preparare la build per mappe offline

Quando si dispone di Internet, eseguire una sola volta:

```powershell
powershell -ExecutionPolicy Bypass -File .\PREPARA_MAPPA_OFFLINE_WINDOWS.ps1
```

Lo script scarica le librerie JavaScript nel progetto e sostituisce `map.html` con la variante completamente locale. Dopo la compilazione, queste librerie vengono incorporate nell'app e non devono più essere scaricate sul portatile operativo. Su macOS usare `./PREPARA_MAPPA_OFFLINE_MACOS.sh`.

## macOS

La build Mac Catalyst deve essere eseguita su un Mac compatibile con Xcode. Il livello seriale è isolato in `Services/SerialTransport.cs`; se Mac Catalyst limita l'accesso diretto alla seriale USB in uno scenario di distribuzione/sandbox, potrà essere sostituito con un adapter nativo senza modificare protocollo, polling, mappe, CSV o GPX.

## Dati registrati

CSV:

`FileSystem.AppDataDirectory/data/YYYY-MM-DD/YYYY-MM-DD_HH-mm-ss_Contatto.csv`

GPX:

`FileSystem.AppDataDirectory/exports/MeshCoreTracks_YYYY-MM-DD_HH-mm-ss.gpx`

Il pulsante GPX apre inoltre il pannello di condivisione/esportazione del sistema.

## Test iniziale consigliato

1. Collegare il WIO L1 PRO Companion USB.
2. Avviare l'app Windows.
3. `Aggiorna` -> scegliere COM -> `Connetti`.
4. Verificare che compaiano tutti i contatti, inclusi GaucsFig1/2/3.
5. Selezionare GaucsFig1/2/3 per il polling.
6. IntPing = 15 s.
7. `Avvia`.
8. Verificare che la barra stato mostri Fig1 -> Fig2 -> Fig3 in sequenza e che tutte le coordinate vengano aggiornate.

Questa versione è pensata come baseline MAUI da confrontare con la Python v2.1, già verificata sul dispositivo reale.

## Correzione build 1.1

La versione 1.1 seleziona il target in base al sistema operativo di sviluppo:

- Windows: `net10.0-windows10.0.19041.0`
- macOS: `net10.0-maccatalyst`

Questo evita che un PC Windows debba ripristinare il workload Mac Catalyst solo per compilare la versione Windows.

Su Windows il workload .NET MAUI resta obbligatorio. Usare `VERIFICA_AMBIENTE_WINDOWS.ps1` per controllare SDK e workload installati.


## Correzione 1.2

Il modello `Contact` è stato rinominato in `MeshContact` per evitare il conflitto con `Microsoft.Maui.ApplicationModel.Communication.Contact`.


## 1.3
- Corretto il contrasto della barra laterale su Windows/MAUI con stili espliciti per pulsanti, picker, entry, label e checkbox.
- I pulsanti disabilitati restano visibili con contrasto sufficiente.


## 1.4
- Aggiunto supporto GeoTIFF EPSG:23032 (ED50 / UTM zona 32N) e EPSG:23033.
- Il messaggio di caricamento mostra ora il CRS proiettato rilevato e, se disponibile, il CRS geografico di base.
- Conversione ED50 -> WGS84 tramite Proj4 con trasformazione a 3 parametri per uso cartografico operativo. Per lavori geodetici ad alta precisione è preferibile una trasformazione ufficiale/griglia specifica dell'area.


## 1.5 — EXE singolo Windows
- Aggiunto `PUBBLICA_EXE_SINGOLO_WINDOWS.bat/.ps1`.
- Pubblicazione Windows x64 unpackaged, self-contained e `PublishSingleFile`.
- Output finale: `DIST_EXE\MeshCoreTracker.exe`.


## Versione 1.6 - distribuzione Windows affidabile

L'EXE MAUI/WinUI unpackaged puo' richiedere il Microsoft Visual C++ Redistributable.
Per questo la distribuzione consigliata e' ora un singolo installer EXE.

Procedura:
1. Con Internet disponibile, eseguire `SCARICA_VC_REDIST_WINDOWS.ps1` una volta.
2. Installare Inno Setup 6 sul PC di sviluppo.
3. Eseguire `CREA_SETUP_EXE_WINDOWS.bat`.
4. Distribuire solamente `DIST_SETUP\MeshCoreTracker_Setup.exe`.

Per diagnosi:
- `PUBBLICA_CARTELLA_WINDOWS.bat` crea `DIST_APP` senza single-file.
- Se `DIST_APP\MeshCoreTracker.exe` parte ma il vecchio EXE singolo no, il problema e' il bundling single-file.
- `DIAGNOSTICA_SXS.bat` crea `MeshCoreTracker_SxS.txt` con `sxstrace.exe`.


## 1.6.1
- Aggiunto `SCARICA_VC_REDIST_WINDOWS.bat`, che usa `curl.exe` e non è soggetto alla PowerShell Execution Policy.
- In alternativa gli script `.ps1` possono essere avviati con `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`.


## 1.6.2
- Sidebar: barra di scorrimento verticale sempre visibile su Windows.
- La rotella del mouse continua a funzionare e la scrollbar può essere trascinata direttamente.
- Padding destro aumentato per lasciare spazio alla scrollbar.
