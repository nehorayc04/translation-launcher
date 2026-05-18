; ============================================================================
;  Translation Manager — Inno Setup script
;
;  Builds a branded, Hebrew-first Windows installer with a custom dark/neon
;  cyberpunk wizard skin.
;
;  Inputs:
;     dist\TranslationManager.exe       (produced by build_exe.bat)
;     build_assets\wizard-large.bmp     (164 x 314)
;     build_assets\wizard-small.bmp     (150 x 57)
;     build_assets\app.ico
;
;  Compile:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;     → Output\TranslationManager-Setup-1.0.0.exe
; ============================================================================

#define AppName        "Translation Manager"
#define AppNameHe      "מנהל התרגומים"
#define AppVersion     "1.0.7"
#define AppPublisher   "Nahorai"
#define AppExeName     "TranslationManager.exe"
#define AppURL         "https://hebrew-translation-hub.vercel.app/"
#define AppId          "{{B0D4F2A7-3CCE-4A1A-9C44-7E1A1B6F0001}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVerName={#AppName} {#AppVersion}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; --- Install location ---
DefaultDirName={autopf}\Translation Manager
DefaultGroupName=Translation Manager
DisableProgramGroupPage=no
DisableDirPage=no
AllowNoIcons=yes

; --- Output ---
OutputDir=Output
OutputBaseFilename=TranslationManager-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; --- Privileges ---
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; --- Branding ---
WizardStyle=modern
WizardImageFile=build_assets\wizard-large.bmp
WizardSmallImageFile=build_assets\wizard-small.bmp
WizardImageStretch=yes
WizardImageAlphaFormat=defined
SetupIconFile=build_assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
AppCopyright=Copyright (C) 2026 {#AppPublisher}

; --- Uninstall behavior ---
CreateUninstallRegKey=yes
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
CloseApplications=yes
RestartApplications=yes

; --- Misc ---
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage
MinVersion=10.0
DisableWelcomePage=no
DisableReadyPage=no
DisableFinishedPage=no

[Languages]
Name: "hebrew";  MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "{cm:CreateDesktopIcon}";                GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}";          GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "startmenuicon"; Description: "Start Menu shortcut";                    GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "autorun";       Description: "הפעל את התוכנה אוטומטית עם הפעלת Windows"; GroupDescription: "אפשרויות נוספות:"; Flags: unchecked

[Files]
; Main bundled executable produced by PyInstaller.
Source: "dist\{#AppExeName}";          DestDir: "{app}"; Flags: ignoreversion
; License / readme (optional — only copied if present at compile time)
Source: "README.md";                   DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; The branding icon copy that the launcher can reference at runtime
Source: "build_assets\app.ico";        DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu group
Name: "{group}\{#AppName}";                Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; Tasks: startmenuicon
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}";  Tasks: startmenuicon

; Desktop shortcut
Name: "{autodesktop}\{#AppName}";          Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

; Quick Launch (legacy, Windows <= 7)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; Tasks: quicklaunchicon

[Registry]
; Optional auto-run with Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TranslationManager"; ValueData: """{app}\{#AppExeName}"""; Tasks: autorun; Flags: uninsdeletevalue

[Run]
; "Launch now" checkbox on the final wizard page
Filename: "{app}\{#AppExeName}"; Description: "הפעל את {#AppNameHe} עכשיו"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean any caches the launcher writes inside its own folder
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files;          Name: "{app}\*.log"

; ============================================================================
;  Custom messages (Hebrew + English)
; ============================================================================
[CustomMessages]
hebrew.AppDescription=מנהל תרגומים לעברית — מאגד עליך את כל התרגומים הקהילתיים למשחקי AAA במקום אחד.
english.AppDescription=Hebrew translations manager — bundles community AAA-game translations in one launcher.

hebrew.LaunchAfterInstall=הפעל את %1 לאחר ההתקנה
english.LaunchAfterInstall=Launch %1 after installation
