# Runs INSIDE the fresh Windows Sandbox on logon (mapped read-only at C:\QA).
# It does NOT auto-install - you run the installer yourself so you see the exact
# real-user flow (SmartScreen, wizard, first boot).

$ErrorActionPreference = 'SilentlyContinue'

# Pick the newest installer that was mapped in from the host Output folder.
$exe = Get-ChildItem 'C:\Installer\TranslationManager-Setup-*.exe' |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1

$msg = @"
=== Translation Manager - clean-machine smoke test ===

Installer: $($exe.FullName)

DO THIS (mirrors a real user on a fresh PC):
 1. Run the installer above -> finish the wizard -> let it launch.
 2. Watch it BOOT: no white screen, no crash, the sidebar + home render.
 3. Settings -> Performance ("ביצועים"): the GPU line will say SOFTWARE here.
    That is EXPECTED in a VM (no real GPU) and is NOT a user bug.
 4. Try Google login: browser opens, "Cancel & back" works, "Copy link" copies.
 5. Open a game panel, switch language, browse Downloads - nothing crashes.
 6. Uninstall via Settings > Apps -> confirm nothing is left behind.

To test the REAL SmartScreen "Unknown publisher" prompt, the mapped file has no
mark-of-the-web so it stays quiet. Download from the release instead:
  irm 'https://github.com/hebrew-translation-hub/translation-launcher/releases/download/v1.0.1-beta/TranslationManager-Setup-1.0.1.exe' -OutFile "$env:USERPROFILE\Downloads\setup.exe" ; & "$env:USERPROFILE\Downloads\setup.exe"

Logs to grab if something breaks:
  %USERPROFILE%\.translation_manager\*.log   (launcher.log, auth_debug.log)
"@

$desk = [Environment]::GetFolderPath('Desktop')
$msg | Out-File "$desk\SMOKE-TEST.txt" -Encoding UTF8
Write-Host $msg
Start-Process explorer.exe 'C:\Installer'
