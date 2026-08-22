; Inno Setup installer for the Community Compute desktop worker.
; Per-user install (no admin / no UAC) — friendly for a volunteer tool.
#define AppName "Community Compute"
#define AppNameHe "מחשוב קהילתי"
#define AppVersion "1.0.3"
#define AppExe "CommunityCompute.exe"

[Setup]
AppId={{B7E2A9C4-4F1E-4C2A-9D3B-CC77E0F13A55}
AppName={#AppNameHe}
AppVersion={#AppVersion}
AppPublisher=Hebrew Translation Hub
DefaultDirName={autopf}\Community Compute
DefaultGroupName={#AppNameHe}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=CommunityCompute-Setup-{#AppVersion}
SetupIconFile=..\..\build_assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "hebrew"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "צור קיצור-דרך בשולחן העבודה"; GroupDescription: "קיצורי דרך:"
Name: "startup"; Description: "הפעל אוטומטית עם עליית המערכת"; GroupDescription: "אפשרויות:"; Flags: unchecked

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppNameHe}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppNameHe}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppNameHe}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "הפעל את {#AppNameHe}"; Flags: nowait postinstall skipifsilent
