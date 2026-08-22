# ac2_watchdog.ps1 - strict guard dog for the AC2 6-stream fleet (desktop x3 + vm3 x3).
#
# WHY THIS EXISTS: the existing self-heal only asks "is the process alive?". The failure
# that cost hours was the opposite - every worker was ALIVE and calling the model, but
# ~87% of batches banked nothing, so the fleet produced almost zero while looking healthy.
# This watchdog judges a stream by its OUTPUT, not its heartbeat.
#
# Each tick (default every 5 min):
#   1. LIVENESS  - ensure 3 providers alive on each machine (ac2_ctl.ps1 ensure).
#   2. PROGRESS  - read each stream's banked count from its log; compare with last tick.
#   3. STALL     - alive but no new lines for STALL_TICKS ticks -> kill it; the next tick
#                  (or the machine's own 5-min task) relaunches it clean.
#   4. DRAINED   - a stream that finished its slice is left alone (not a fault).
#   5. PUSHER    - keep ac2_progress.py alive so the dashboard never goes stale.
#   6. STATUS    - write ac2_watchdog_status.json for inspection.
#
# Runs hidden (wscript + hidden.vbs). Never throws: every remote/IO step is guarded, so a
# transient ssh or disk failure degrades to "skip this tick" instead of killing the guard.
# 3 ticks x 5 min = 15 minutes of COMPLETE silence before a worker is recycled. A healthy
# worker prints a line per batch (seconds apart), so this cannot fire on a merely slow one.
param([int]$StallTicks = 3)

$ErrorActionPreference = "SilentlyContinue"
$HERE     = $PSScriptRoot
# NOTE: PowerShell variable names are CASE-INSENSITIVE - a path named $STATE would be
# silently overwritten by a data variable named $state, and the write then fails with no
# error. Keep the path names distinct from the data names.
$StatePath  = Join-Path $HERE 'ac2_watchdog_state.json'
$StatusPath = Join-Path $HERE 'ac2_watchdog_status.json'
$LOG      = 'C:\tmp\ac2_watchdog.log'
$KEY      = 'C:\Users\Nehoray_Cohen\.ssh\id_ed25519'   # absolute: the task may run as SYSTEM
$SSHOPT   = @('-i', $KEY, '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20')
# ssh is NOT on PATH in a PowerShell/SYSTEM context - resolve it by absolute path, or every
# remote check silently reports the VM as DOWN (which is exactly how this bit the first run).
$SSH = @('C:\Windows\System32\OpenSSH\ssh.exe',
         'C:\Program Files\Git\usr\bin\ssh.exe',
         'C:\Program Files\OpenSSH\ssh.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $SSH) { $SSH = (Get-Command ssh -EA SilentlyContinue).Source }
$PROVIDERS = @('groq', 'sambanova', 'nim')

function Log($m) {
    try { Add-Content -Path $LOG -Value ("{0}  {1}" -f (Get-Date -Format 'MM-dd HH:mm:ss'), $m) -Encoding UTF8 } catch {}
}

# --- progress is read from the worker log: "total <done>/<slice>" is printed per batch ---
function Read-Progress($text) {
    if (-not $text) { return $null }
    $drained = $text -match 'slice drained'
    # "sig" = the tail's last line. A worker that banks nothing but keeps printing batch
    # lines is WORKING (rejecting/parking); one whose log is frozen is genuinely HUNG.
    # Distinguishing the two stops the guard from killing a healthy busy worker.
    $lines = @($text -split "`n" | Where-Object { $_.Trim() })
    $sig = if ($lines.Count) { $lines[-1].Trim() } else { '' }
    $m = [regex]::Matches($text, 'total (\d+)/(\d+)')
    if ($m.Count -eq 0) { return @{ done = $null; drained = $drained; sig = $sig } }
    @{ done = [int]$m[$m.Count - 1].Groups[1].Value; drained = $drained; sig = $sig }
}

# ---------------------------------------------------------------- desktop (local) ----
function Get-DesktopStreams {
    $out = @{}
    foreach ($p in $PROVIDERS) {
        $f = "C:\tmp\ac2_desktop_$p.log"
        $tail = try { (Get-Content $f -Tail 40 -EA Stop) -join "`n" } catch { $null }
        $out[$p] = Read-Progress $tail
    }
    $out
}
function Get-DesktopAlive {
    $live = @{}
    Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -match 'ac2_nim' } | ForEach-Object {
            foreach ($p in $PROVIDERS) { if ($_.CommandLine -match "ac2_nim\.py\s+$p\b") { $live[$p] = $_.ProcessId } }
        }
    $live
}

# -------------------------------------------------------------------- vm3 (remote) ----
function Invoke-Vm($cmd) {
    if (-not $SSH) { return $null }
    try { & $SSH @SSHOPT -p 2224 vboxuser@127.0.0.1 $cmd 2>$null } catch { $null }
}
function Get-VmStreams {
    $out = @{}
    foreach ($p in $PROVIDERS) {
        $t = Invoke-Vm "powershell -NoProfile -Command `"Get-Content C:\ac2w\w_$p.log -Tail 40`""
        $out[$p] = Read-Progress ($t -join "`n")
    }
    $out
}
function Get-VmAlive {
    $t = Invoke-Vm 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\ac2w\ac2_ctl.ps1 list'
    $live = @{}
    foreach ($line in @($t)) {
        foreach ($p in $PROVIDERS) { if ($line -match "^$p\s+pid\s+(\d+)") { $live[$p] = [int]$Matches[1] } }
    }
    $live
}

# ------------------------------------------------------------------------- the tick ---
$prev = @{}
try { $prev = (Get-Content $StatePath -Raw | ConvertFrom-Json) } catch {}
function PrevStalls($id) { try { [int]$prev.$id } catch { 0 } }

$state  = @{}
$report = @()
$actions = @()

foreach ($machine in @('desktop', 'vm3')) {
    $streams = if ($machine -eq 'desktop') { Get-DesktopStreams } else { Get-VmStreams }
    $alive   = if ($machine -eq 'desktop') { Get-DesktopAlive }   else { Get-VmAlive }

    foreach ($p in $PROVIDERS) {
        $id   = "$machine/$p"
        $s    = $streams[$p]
        $isUp = $alive.ContainsKey($p)
        $done = if ($s) { $s.done } else { $null }
        $drained = if ($s) { [bool]$s.drained } else { $false }

        # a stream that finished its slice is DONE, not broken
        if ($drained -and -not $isUp) {
            $report += "$id : drained (complete)"
            $state["done_$id"] = $done
            continue
        }

        $prevDone = try { [int]$prev."done_$id" } catch { $null }
        $prevSig  = try { [string]$prev."sig_$id" } catch { $null }
        $sig      = if ($s) { [string]$s.sig } else { '' }
        $stalls   = PrevStalls "stall_$id"
        # frozen = banked nothing AND wrote nothing since last tick => genuinely hung
        $frozen   = ($null -ne $prevSig) -and ($sig -eq $prevSig)

        if ($isUp -and $frozen -and $null -ne $done -and $null -ne $prevDone -and $done -le $prevDone) {
            $stalls++
            if ($stalls -ge $StallTicks) {
                # ALIVE BUT NOT PRODUCING -> recycle it; ensure (below) brings it back clean
                if ($machine -eq 'desktop') {
                    Stop-Process -Id $alive[$p] -Force
                } else {
                    Invoke-Vm "powershell -NoProfile -Command `"Stop-Process -Id $($alive[$p]) -Force`"" | Out-Null
                }
                $actions += "$id : STALLED at $done for $stalls ticks -> killed for relaunch"
                Log "STALL $id done=$done ticks=$stalls -> killed pid $($alive[$p])"
                $stalls = 0
            } else {
                $report += "$id : FROZEN - no output (${stalls}/$StallTicks)"
            }
        } else {
            $stalls = 0
            $delta = if ($null -ne $prevDone -and $null -ne $done) { $done - $prevDone } else { 0 }
            $note  = if ($isUp) { if ($delta -gt 0) { "up" } else { "up/working" } } else { "DOWN" }
            $report += "$id : $note done=$done (+$delta)"
        }

        $state["done_$id"]  = $done
        $state["stall_$id"] = $stalls
        $state["sig_$id"]   = $sig
    }
}

# --- LIVENESS: bring any missing provider back (idempotent; singleton lock protects) ---
try {
    $r = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $HERE 'ac2_ctl.ps1') ensure 2>$null
    if ($r -notmatch 'already alive') { $actions += "desktop ensure: $r"; Log "desktop ensure -> $r" }
} catch {}
try {
    $r = Invoke-Vm 'powershell -NoProfile -ExecutionPolicy Bypass -File C:\ac2w\ac2_ctl.ps1 ensure'
    if ($r -and ($r -notmatch 'already alive')) {
        # a worker launched over ssh dies with the session -> use the SYSTEM task instead
        Invoke-Vm 'schtasks /Run /TN AC2MP' | Out-Null
        $actions += "vm3 ensure: $r (via AC2MP)"; Log "vm3 ensure -> $r"
    }
} catch {}

# --- PUSHER: the dashboard must never go stale --------------------------------------
try {
    $push = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
            Where-Object { $_.CommandLine -match 'ac2_progress' }
    if (-not $push) {
        Start-Process wscript.exe -ArgumentList "`"$HERE\hidden.vbs`"", "`"$HERE\run_ac2_progress.bat`"" -WindowStyle Hidden
        $actions += 'pusher was down -> restarted'; Log 'pusher restarted'
    }
} catch {}

# --- persist -------------------------------------------------------------------------
try { $state | ConvertTo-Json -Compress | Set-Content $StatePath -Encoding UTF8 } catch {}
try {
    @{ at = (Get-Date -Format 's'); streams = $report; actions = $actions } |
        ConvertTo-Json -Depth 4 | Set-Content $StatusPath -Encoding UTF8
} catch {}
if ($actions.Count) { Log ("actions: " + ($actions -join ' | ')) }
$report | ForEach-Object { $_ }
$actions | ForEach-Object { "ACTION: $_" }
