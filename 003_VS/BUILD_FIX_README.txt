MESHCORE TRACKER MAUI 1.1 - FIX BUILD WINDOWS

Questa versione modifica il progetto per compilare SOLO il target nativo del sistema di sviluppo:
- su Windows: net10.0-windows10.0.19041.0
- su macOS:  net10.0-maccatalyst

Questo evita che Visual Studio su Windows tenti di ripristinare anche il workload Mac Catalyst.

PREREQUISITO WINDOWS
--------------------
Serve il workload .NET MAUI installato.
Metodo consigliato:
1. Chiudere Visual Studio.
2. Aprire Visual Studio Installer.
3. Selezionare Modifica sull'installazione di Visual Studio.
4. Installare il workload '.NET Multi-platform App UI development' / '.NET MAUI'.
5. Assicurarsi che sia installato anche .NET 10 SDK.
6. Riavviare Visual Studio.

VERIFICA
--------
Eseguire in PowerShell:
  .\VERIFICA_AMBIENTE_WINDOWS.ps1

Tra i workload installati deve comparire almeno 'maui-windows' oppure 'maui'.

Poi aprire MeshCoreTracker.sln e compilare Windows Machine.
In alternativa:
  .\BUILD_WINDOWS.ps1

NOTA
----
Non usare contemporaneamente Visual Studio Installer e 'dotnet workload install maui'
per riparare la stessa installazione se MAUI era gia' gestito da Visual Studio Installer.
