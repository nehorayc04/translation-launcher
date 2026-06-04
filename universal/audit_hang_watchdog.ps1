# ===================================================================
# audit_hang_watchdog.ps1
# Polls cross_audit_checkpoint.json's mtime once a minute. If the
# checkpoint hasn't been written for more than HANG_SECONDS, kills the
# audit's python.exe - start_audit.bat's supervisor loop then catches
# the exit and relaunches the script.
#
# Why this is needed: the audit's per-row retry budget is bounded
# (3 x ~120s = ~6 min for one stuck row), but a chain of stuck rows
# can multiply that into hours, and a deeper hang in the OpenAI SDK's
# HTTP layer can hold the script forever without it crashing. The
# supervisor only restarts on EXIT, so a hung-but-alive script keeps
# the website's quality-control row frozen indefinitely. This
# watchdog converts a hang into an exit.
# ===================================================================
$ErrorActionPreference = 'Continue'
$root          = Split-Path -Parent $MyInvocation.MyCommand.Path
$ckpt          = Join-Path $root 'cross_audit_checkpoint.json'
# Separate log file: start_audit.bat keeps audit.log open with `>>` for
# append; on Windows that holds an exclusive-ish handle that makes
# Add-Content from PowerShell fail silently. Owning our own file
# guarantees every tick lands.
$log           = Join-Path $root 'audit_watchdog.log'
$HangSeconds   = if ($env:AUDIT_HANG_SECONDS) { [int]$env:AUDIT_HANG_SECONDS } else { 360 }
$PollSeconds   = 60

function Write-Log {
  param([string]$msg)
  $line = "[{0}] [watchdog] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
  Write-Host $line
  try { Add-Content -LiteralPath $log -Value $line -Encoding UTF8 -ErrorAction Stop } catch {}
}

Write-Log ("started - checking every {0}s, hang threshold {1}s" -f $PollSeconds, $HangSeconds)

while ($true) {
  Start-Sleep -Seconds $PollSeconds
  try {
    if (-not (Test-Path -LiteralPath $ckpt)) { continue }
    $age = ((Get-Date) - (Get-Item -LiteralPath $ckpt).LastWriteTime).TotalSeconds
    if ($age -lt $HangSeconds) { continue }

    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
             Where-Object { $_.CommandLine -match 'continuous_audit_loop' }
    if (-not $procs) { continue }

    $msg = "HANG DETECTED - checkpoint age {0}s > {1}s threshold; killing audit" -f [int]$age, $HangSeconds
    Write-Log $msg
    foreach ($p in $procs) {
      Write-Log ("  killing PID {0}" -f $p.ProcessId)
      Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    # Give the supervisor 30s to relaunch + the new audit a few minutes
    # to settle (preflight + first batch) before judging hung again.
    Start-Sleep -Seconds 240
  } catch {
    Write-Log ("tick raised {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
  }
}
