# _check_single.ps1
# Singleton helper for monitor_supervisor.bat and start_audit.bat.
# Exits 0 if this is the only cmd.exe whose CommandLine matches $Pattern,
# exits 1 if there's already another one running so the caller knows to
# bail out instead of starting a duplicate supervisor loop.
#
# Background: tonight's adversarial workflow caught a race where the
# user (or a stray double-click from explorer.exe) launched a SECOND
# monitor_supervisor.bat 35 s after the first. With no singleton guard
# both supervisors would have spawned independent monitor processes,
# producing duplicate POSTs to /api/admin/progress every 60 s.
#
# Usage from a .bat:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_check_single.ps1" monitor_supervisor
#   if errorlevel 1 ( exit /b 0 )
param(
  [Parameter(Mandatory)][string]$Pattern
)
$matching = @(Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
              Where-Object { $_.CommandLine -like "*$Pattern*" })
if ($matching.Count -gt 1) { exit 1 } else { exit 0 }
