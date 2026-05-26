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
#define AppURL         "https://hebrew-translation-hub.com/"
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
; runasoriginaluser: the installer runs elevated (admin), but the launcher
; must NOT — running it as admin breaks drag-drop from Explorer and shifts
; the single-instance mutex namespace. This flag relaunches it with the
; normal (non-elevated) credentials of the user who started Setup, which is
; also correct for the in-app self-update path (the launcher spawns the
; installer non-elevated, it elevates via UAC, then relaunches as the user).
Filename: "{app}\{#AppExeName}"; Description: "הפעל את {#AppNameHe} עכשיו"; Flags: nowait postinstall runasoriginaluser

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
// Poll-kill the launcher process tree until taskkill reports nothing left.
// Does NOT touch {app} — safe to call from InitializeSetup, where the user
// has not yet picked an install directory and {app} is still uninitialized.
procedure KillLauncherProcesses;
var
  rc, i: Integer;
begin
  for i := 1 to 25 do
  begin
    rc := -1;
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM {#AppExeName}',
         '', SW_HIDE, ewWaitUntilTerminated, rc);
    if rc <> 0 then
      Break;            // taskkill found no process → launcher is gone
    Sleep(250);
  end;
  // Settle: let Windows + antivirus release the handles the killed tree held.
  Sleep(1500);
end;

// File-lock probe on {app}\TranslationManager.exe. Renaming to a temp name
// and back succeeds ONLY when nothing holds the file open. Requires {app}
// to be initialized — call ONLY from PrepareToInstall onwards.
procedure WaitForLauncherUnlocked;
var
  i: Integer;
  exePath, probePath: String;
begin
  exePath   := ExpandConstant('{app}\{#AppExeName}');
  probePath := exePath + '.killprobe';
  if FileExists(exePath) then
  begin
    DeleteFile(probePath);   // clear any leftover probe from a prior run
    for i := 1 to 20 do
    begin
      if RenameFile(exePath, probePath) then
      begin
        RenameFile(probePath, exePath);   // unlocked → put it back, done
        Break;
      end;
      Sleep(300);
    end;
  end;
end;

function InitializeSetup(): Boolean;
begin
  // Kill the running launcher BEFORE the wizard even appears, so it can
  // never hold _internal\*.pyd handles open during the file copy. This
  // is the primary fix for "installer finishes but the old app is still
  // running" — CloseApplications=no means the Restart Manager won't.
  // {app} is NOT yet initialized here — must NOT call WaitForLauncherUnlocked.
  KillLauncherProcesses;
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // Kill again right before the copy — covers the user reopening the
  // launcher while clicking through the wizard pages. {app} IS initialized
  // by this stage, so the file-lock probe is safe here.
  KillLauncherProcesses;
  WaitForLauncherUnlocked;
end;
