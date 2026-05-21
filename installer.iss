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
#define AppVersion     "1.1.0"
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
; CloseApplications is OFF on purpose: the launcher minimises to the
; system tray on window-close, so the Restart Manager closes the WINDOW
; but the process survives holding _internal\*.pyd open. We kill it
; ourselves in [Code] (InitializeSetup + PrepareToInstall) instead.
CloseApplications=no
RestartApplications=no

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
; Onedir bundle produced by PyInstaller — copies the whole directory
; tree (TranslationManager.exe + _internal/) into the install folder.
; recursesubdirs + createallsubdirs is what makes the Inno Setup install
; progress bar stream a rapid list of files instead of hanging on a
; single multi-hundred-MB encrypted blob.
Source: "dist\TranslationManager\*";   DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
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
; "Launch now" checkbox on the final wizard page.
;
; NOTE: deliberately NOT flagged `skipifsilent`. The in-app self-updater
; runs this installer with /VERYSILENT — and after a silent self-update
; we WANT the freshly-installed launcher to relaunch automatically (so
; the user lands back where they were). With `postinstall` + the default
; checked state and no `skipifsilent`, Inno runs this entry on silent
; installs too. Interactive installs still show it as the usual
; "Launch now" checkbox on the Finished page.
Filename: "{app}\{#AppExeName}"; Description: "הפעל את {#AppNameHe} עכשיו"; Flags: nowait postinstall

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

; ============================================================================
;  Code — force-close a running launcher before the file copy.
;
;  The launcher minimises to the system tray on window-close, so Inno's
;  built-in Restart Manager (CloseApplications=yes) sees the Chromium
;  window vanish and assumes the app closed — but the Python process is
;  still alive in the tray, holding _internal\*.pyd handles open. The
;  copy step then fails with a "file in use" error EVEN AFTER the user
;  accepted the close-applications prompt. That is exactly the bug being
;  fixed here.
;
;  PrepareToInstall runs right after the user clicks "Install" and right
;  before any file is touched — the correct, last-chance hook. taskkill
;  /T tears down the whole process tree (Chromium --app child, gevent
;  worker, tray thread); /F forces it. The call is best-effort: if the
;  launcher isn't running, taskkill simply returns non-zero and we move
;  on. [Code] must be the LAST section in the script — anything after it
;  is parsed as Pascal.
; ============================================================================
[Code]
procedure KillRunningLauncher;
var
  ResultCode: Integer;
begin
  // Two passes: the launcher minimises to the tray, and a single-instance
  // relaunch can briefly respawn it — a second kill catches that race.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExeName}',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExeName}',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeSetup(): Boolean;
begin
  // Kill the running launcher BEFORE the wizard even appears, so it can
  // never hold _internal\*.pyd handles open during the file copy. This
  // is the primary fix for "installer finishes but the old app is still
  // running" — CloseApplications=no means the Restart Manager won't.
  KillRunningLauncher;
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Kill again right before the copy — covers the user reopening the
  // launcher while clicking through the wizard pages.
  KillRunningLauncher;
  // Give Windows a beat to release the handles the killed tree held.
  Sleep(800);
end;
