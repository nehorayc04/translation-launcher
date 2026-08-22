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
#define AppVersion     "1.2.0"
; PROJECT identity only - never a personal name. This string is user-visible in
; the installer, in Add/Remove Programs and in the exe's copyright field.
#define AppPublisher   "Hebrew Translation Hub"
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
; Inno APPENDS each install's records to unins000.dat, so an app that updates
; often grows a huge uninstall log for nothing (measured here: 161 MB after a
; handful of updates - bigger than the program itself). "overwrite" replaces it
; instead, which is exactly right for us: [InstallDelete] wipes {app}\_internal
; and [Files] re-copies the WHOLE tree, so the newest log alone already describes
; everything on disk. (NOT "new" - that mode writes unins001/002/... i.e. a fresh
; uninstaller PAIR per install, which accumulates even faster.)
UninstallLogMode=overwrite

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
; Windows 10 1809 (build 17763) is the floor for Qt6 + QtWebEngine (Chromium).
; Below it the bundled runtime fails to load with a cryptic DLL error, so we
; refuse at install time with a clean "unsupported Windows" message instead.
; 1809 is long EOL, so this excludes only ancient builds the app can't run on.
MinVersion=10.0.17763
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
Name: "biglaunchicon"; Description: "קיצור דרך לביג-לאנץ (מסך מלא) בשולחן העבודה"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autorun";       Description: "הפעל את התוכנה אוטומטית עם הפעלת Windows"; GroupDescription: "אפשרויות נוספות:"; Flags: unchecked

[InstallDelete]
; The web bundle is emitted with a CONTENT HASH in its filename
; (assets/index-<hash>.js), so every build produces a NEW name. Inno only adds
; and overwrites — it never removes what a previous version left behind — so
; each update used to leave its predecessor's bundle on disk FOREVER. Measured
; on a dev machine after many builds: 132 stale .js files, 61 MB of dead code
; shipped around forever, and a real user's install grows a little with every
; update. Wiping the hashed-asset dir before the copy guarantees only the
; CURRENT build's assets exist. Runs before [Files], which recreates it.
;
; The SAME leak applies to every file the bundle stops shipping: dropping numpy,
; tkinter/tcl-tk, 51 Chromium locale packs and the DevTools pak cut the payload
; by ~100 MB, yet an in-place update left ALL of it behind as orphans (measured:
; a 511 MB install dir weighing 1,036 MB after the upgrade). `_internal` holds
; ONLY program files — the writable cache is {app}\data and user state lives in
; %USERPROFILE%\.translation_manager — so wiping the whole tree before [Files]
; is safe and makes every install byte-identical to a fresh one.
Type: filesandordirs; Name: "{app}\_internal"

[Dirs]
; Ubisoft-style writable data folder: game covers/banners/logos and the
; QtWebEngine disk cache live here at runtime — they are NOT bundled in the
; installer (keeps the download small). Granted Users-modify so the
; non-elevated launcher can write it; delete this folder and the launcher
; simply re-downloads everything from the server on the next run.
Name: "{app}\data"; Permissions: users-modify

[Files]
; Onedir bundle produced by PyInstaller — copies the whole directory
; tree (TranslationManager.exe + _internal/) into the install folder.
; recursesubdirs + createallsubdirs is what makes the Inno Setup install
; progress bar stream a rapid list of files instead of hanging on a
; single multi-hundred-MB encrypted blob.
; Exclude the runtime-created `data\` cache (covers/banners/QtWebEngine) — it
; must never be bundled (that's the whole point of streaming it from the
; server) and it would also be file-locked if the launcher is running.
Source: "dist\TranslationManager\*";   DestDir: "{app}"; Excludes: "\data\*,\data"; Flags: ignoreversion recursesubdirs createallsubdirs
; License / readme (optional — only copied if present at compile time)
Source: "README.md";                   DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; The branding icon copy that the launcher can reference at runtime
Source: "build_assets\app.ico";        DestDir: "{app}"; Flags: ignoreversion
; "ביג-לאנץ" - the console shell, its OWN executable (the Steam / Big Picture
; shape). Single-file, framework-dependent .NET 8 WPF; it sits beside
; TranslationManager.exe, which is exactly where main_eel._big_launch_exe()
; looks for it. skipifsourcedoesntexist so the launcher still builds if the
; native shell wasn't published in this run. The .pdb is a debug symbol file -
; never shipped.
Source: "dist_biglaunch\BigLaunch.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
; The sparse (external-location) package that gives BigLaunch.exe a package
; IDENTITY, which is what lets Windows list it under
; הגדרות > משחקים > מצב XBOX > "בחר אפליקציית בית" next to XBOX itself.
; It contains no code - only a manifest, tile art and the capability descriptor,
; and it points back at THIS folder ({app}) at registration time. Big Launch only:
; a home app is what the full-screen experience boots into and drives with a pad.
Source: "tools\msix\*";                DestDir: "{app}\msix"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; 🔴 THE DESCRIPTOR AND THE TILE ART MUST SIT IN THE INSTALL FOLDER, NOT ONLY
; BESIDE THE MANIFEST. Deployment searches "<ExternalLocation>\*.sccd" (otherwise
; registration fails with a "cannot find the file specified" that names no file),
; and the picker resolves the logo from "<ExternalLocation>\Assets" - without it
; the entry appears with the generic placeholder icon instead of ours.
Source: "tools\msix\biglaunch\CustomCapability.SCCD"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "tools\msix\biglaunch\Assets\*"; DestDir: "{app}\Assets"; Flags: ignoreversion skipifsourcedoesntexist
; Unpacks an OFFLINE PACKAGE appended to this very .exe (see the [Run] entry).
; Temp-only: it is a build-time helper, never part of the installed program.
Source: "build_assets\tm_offline_deploy.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
; Start Menu group
; AppUserModelID MUST match main_qt.APP_USER_MODEL_ID - Windows pairs the
; shortcut's AUMID with the one the process declares to decide whether to SHOW a
; tray toast. Mismatched (or missing) => native notifications are silently
; dropped and the app never appears under Settings -> System -> Notifications.
Name: "{group}\{#AppName}";                Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; AppUserModelID: "HebrewTranslationHub.TranslationManager"; Tasks: startmenuicon
; "ביג-לאנץ" - the SEPARATE console shell, its OWN executable, exactly like
; Steam vs Big Picture: two programs, two shortcuts, either can start on its own
; and hand off to the other. Its own AppUserModelID so Windows gives it a
; DISTINCT taskbar identity instead of merging it into the launcher's button.
Name: "{group}\{#AppName} - ביג-לאנץ";     Filename: "{app}\BigLaunch.exe"; IconFilename: "{app}\app.ico"; AppUserModelID: "HebrewTranslationHub.BigLaunch"; Comment: "ממשק קונסולה במסך מלא - ניווט בשלט מהספה"; Tasks: startmenuicon
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}";  Tasks: startmenuicon

; Desktop shortcut
Name: "{autodesktop}\{#AppName}";          Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; AppUserModelID: "HebrewTranslationHub.TranslationManager"; Tasks: desktopicon
Name: "{autodesktop}\{#AppName} - ביג-לאנץ"; Filename: "{app}\BigLaunch.exe"; IconFilename: "{app}\app.ico"; AppUserModelID: "HebrewTranslationHub.BigLaunch"; Comment: "ממשק קונסולה במסך מלא - ניווט בשלט מהספה"; Tasks: biglaunchicon

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
; OFFLINE PACKAGE. The website can hand a visitor ONE file: this installer with
; the translations they picked APPENDED to it ([setup][zip][int64 len][magic]).
; Appended bytes are inert for Inno (it addresses its own data by header
; offsets - verified: an installer with 2 MB appended installs normally), so the
; same .exe is still a perfectly ordinary installer when nothing is attached.
; This step unpacks that payload into the launcher's offline store, so an
; offline machine needs no copying, no extracting and no second file.
;   * BEFORE the launch entry, so the app already sees the store on first run.
;   * runasoriginaluser: the store belongs in the profile of the person who will
;     run the launcher, NOT the elevated account that ran Setup.
;   * runhidden + a script that exits 0 on ANY problem: a bonus payload must
;     never be able to fail or even slow down a normal install.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{tmp}\tm_offline_deploy.ps1"" -Setup ""{srcexe}"""; \
  StatusMsg: "מתקין את חבילת התרגומים…"; Flags: runhidden waituntilterminated runasoriginaluser
; HOME-APP REGISTRATION. Puts "Big Launch" into the Windows XBOX-mode home-app
; picker (the console shell only, never the windowed launcher).
; runasoriginaluser because an app package is
; registered PER USER - registering as the elevated account would hand the entry
; to the wrong profile. runhidden + a script that swallows its own errors: this
; is an extra, and a machine that is not developer-unlocked simply does not get
; it. Before the launch entry, so the picker is already populated on first run.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\msix\register.ps1"" -InstallDir ""{app}"""; \
  StatusMsg: "רושם את מצב הטלוויזיה במערכת…"; Flags: runhidden waituntilterminated runasoriginaluser
Filename: "{app}\{#AppExeName}"; Description: "הפעל את {#AppNameHe} עכשיו"; Flags: nowait postinstall runasoriginaluser

[UninstallRun]
; Take the entry back out of the picker before the files disappear -
; otherwise Windows keeps listing a home app whose executable is gone.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\msix\register.ps1"" -InstallDir ""{app}"" -Unregister"; \
  Flags: runhidden waituntilterminated runasoriginaluser; RunOnceId: "UnregisterHomeApps"

[UninstallDelete]
; Clean any caches the launcher writes inside its own folder
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files;          Name: "{app}\*.log"
; The runtime-created data folder (covers/banners/logos + QtWebEngine cache)
Type: filesandordirs; Name: "{app}\data"

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
  // "ביג-לאנץ" is its OWN process now, and it deliberately outlives the
  // launcher that started it — so it holds its own file lock and must be
  // closed too, or the copy fails on BigLaunch.exe with the launcher already gone.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM BigLaunch.exe',
       '', SW_HIDE, ewWaitUntilTerminated, rc);
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
