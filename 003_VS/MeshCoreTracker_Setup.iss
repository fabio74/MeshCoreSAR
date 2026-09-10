
#define MyAppName "MeshCore Tracker"
#define MyAppVersion "1.6"
#define MyAppExeName "MeshCoreTracker.exe"

[Setup]
AppId={{7E20A4E3-2F14-4AC8-9A3C-6D3C2BCE1601}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\MeshCoreTracker
DefaultGroupName={#MyAppName}
OutputDir=DIST_SETUP
OutputBaseFilename=MeshCoreTracker_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "DIST_APP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Prerequisiti\VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crea icona sul desktop"; GroupDescription: "Collegamenti:"; Flags: unchecked

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installazione/aggiornamento Microsoft Visual C++ Runtime..."; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia {#MyAppName}"; Flags: nowait postinstall skipifsilent
