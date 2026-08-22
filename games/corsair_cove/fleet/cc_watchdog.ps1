# cc_watchdog.ps1 - strict guard dog for the corsair-cove 9-stream fleet (vm/vm2/vm3, 3 providers
# each, all reached over 127.0.0.1:2222/2223/2224). Same design as ac2_watchdog.ps1: judge a
# stream by its OUTPUT, not its heartbeat. "alive" (a python.exe with a matching commandline
# exists) is NOT the same as "producing" - a hung urllib call can leave a process alive that
# writes nothing for 20+ minutes, and the machine's own CcMP task (which only relaunches a
# MISSING worker) can never recover that case because the singleton lock is still held by the
# hung PID. This script runs forever (its own loop, since this shell cannot register a Windows
# Scheduled Task) and every $TickSeconds:
#   1. reads each stream's log tail + a matching python.exe pid, in ONE ssh round-trip/machine
#   2. FROZEN = the log's last line is unchanged AND the banked count did not grow since last tick
#   3. alive + frozen for $StallTicks consecutive ticks (default 3 x 5 min = 15 min of complete
#      silence) -> kill that one pid over ssh, then let CcMP's next run (or our own "ensure"
#      below) relaunch it clean
#   4. never touches a stream that is merely slow but still printing/banking
$TickSeconds = 300
$StallTicks  = 3

$ErrorActionPreference = "SilentlyContinue"
$HERE       = $PSScriptRoot
$StatePath  = Join-Path $HERE 'cc_watchdog_state.json'
$StatusPath = Join-Path $HERE 'cc_watchdog_status.json'
$LOG        = 'C:\tmp\cc_watchdog.log'
$KEY        = 'C:\Users\Nehoray_Cohen\.ssh\id_ed25519'
$SSHOPT     = @('-i', $KEY, '-o', 'StrictHostKeyChecking=no', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20')
$SSH = @('C:\Windows\System32\OpenSSH\ssh.exe',
         'C:\Program Files\Git\usr\bin\ssh.exe',
         'C:\Program Files\OpenSSH\ssh.exe') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $SSH) { $SSH = (Get-Command ssh -EA SilentlyContinue).Source }
$PROVIDERS = @('groq', 'sambanova', 'nim')
$MACHINES  = @{ vm = 2222; vm2 = 2223; vm3 = 2224 }

function Log($m) {
    try { Add-Content -Path $LOG -Value ("{0}  {1}" -f (Get-Date -Format 'MM-dd HH:mm:ss'), $m) -Encoding UTF8 } catch {}
}

function Read-Progress($text) {
    if (-not $text) { return @{ done = $null; sig = '' } }
    $lines = @($text -split "`n" | Where-Object { $_.Trim() })
    $sig = if ($lines.Count) { $lines[-1].Trim() } else { '' }
    $m = [regex]::Matches($text, 'total (\d+)/(\d+)')
    if ($m.Count -eq 0) { return @{ done = $null; sig = $sig } }
    @{ done = [int]$m[$m.Count - 1].Groups[1].Value; sig = $sig }
}

function Get-Remote($port) {
    # ONE ssh round-trip per machine: pid + last-30-lines for all 3 providers, as JSON.
    $cmd = @'
$out = @{}
foreach ($p in @('groq','sambanova','nim')) {
  $proc = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -match ("cc_nim\.py\s+" + $p + "\b") } | Select-Object -First 1
  $out["pid_$p"] = if ($proc) { $proc.ProcessId } else { 0 }
  $out["log_$p"] = try { (Get-Content ("C:\ccw\w_" + $p + ".log") -Tail 30 -EA Stop) -join "`n" } catch { "" }
}
$out | ConvertTo-Json -Compress
'@
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($cmd))
    $r = & $SSH @SSHOPT -p $port vboxuser@127.0.0.1 "powershell -NoProfile -EncodedCommand $b64" 2>$null
    try { ($r -join "") | ConvertFrom-Json } catch { $null }
}

function Invoke-Remote($port, $cmd) {
    if (-not $SSH) { return $null }
    try { & $SSH @SSHOPT -p $port vboxuser@127.0.0.1 $cmd 2>$null } catch { $null }
}

function Tick() {
    $prev = @{}
    try { $prev = (Get-Content $StatePath -Raw | ConvertFrom-Json) } catch {}
    $state = @{}; $report = @(); $actions = @()

    foreach ($machine in $MACHINES.Keys) {
        $port = $MACHINES[$machine]
        $r = Get-Remote $port
        if (-not $r) {
            $report += "$machine : ssh unreachable this tick (skipped, not treated as stalled)"
            continue
        }
        foreach ($p in $PROVIDERS) {
            $id = "$machine/$p"
            $pidv = [int]$r."pid_$p"
            $isUp = $pidv -gt 0
            $s = Read-Progress ([string]$r."log_$p")
            $done = $s.done
            $sig = [string]$s.sig

            $prevDone = try { [int]$prev."done_$id" } catch { $null }
            $prevSig = try { [string]$prev."sig_$id" } catch { $null }
            $stalls = try { [int]$prev."stall_$id" } catch { 0 }
            $frozen = ($null -ne $prevSig) -and ($sig -eq $prevSig) -and ($sig -ne '')

            if ($isUp -and $frozen -and $null -ne $done -and $null -ne $prevDone -and $done -le $prevDone) {
                $stalls++
                if ($stalls -ge $StallTicks) {
                    Invoke-Remote $port "powershell -NoProfile -Command `"Stop-Process -Id $pidv -Force`"" | Out-Null
                    $actions += "$id : STALLED at $done for $stalls ticks -> killed pid $pidv for relaunch"
                    Log "STALL $id done=$done ticks=$stalls -> killed pid $pidv"
                    $stalls = 0
                } else {
                    $report += "$id : FROZEN - no output (${stalls}/$StallTicks)"
                }
            } elseif (-not $isUp) {
                $report += "$id : DOWN (no matching python.exe)"
                $stalls = 0
            } else {
                $stalls = 0
                $delta = if ($null -ne $prevDone -and $null -ne $done) { $done - $prevDone } else { 0 }
                $report += "$id : up done=$done (+$delta)"
            }
            $state["done_$id"] = $done
            $state["stall_$id"] = $stalls
            $state["sig_$id"] = $sig
        }
        # a stream missing entirely (killed above, or genuinely dead) is revived by the
        # machine's OWN CcMP task, which is singleton-lock-protected -> safe to call every tick.
        Invoke-Remote $port 'schtasks /Run /TN CcMP' | Out-Null
    }

    # keep the dashboard pusher alive (matches every other pull_*.sh in this fleet)
    try {
        $push = Get-CimInstance Win32_Process -Filter "name='python.exe'" |
                Where-Object { $_.CommandLine -match 'cc_progress' }
        if (-not $push) {
            Start-Process wscript.exe -ArgumentList "`"$HERE\hidden.vbs`"", "`"$HERE\pull_cc.bat`"" -WindowStyle Hidden
            $actions += 'pusher was down -> restarted via pull_cc.bat'
        }
    } catch {}

    try { $state | ConvertTo-Json -Compress | Set-Content $StatePath -Encoding UTF8 } catch {}
    try {
        @{ at = (Get-Date -Format 's'); streams = $report; actions = $actions } |
            ConvertTo-Json -Depth 4 | Set-Content $StatusPath -Encoding UTF8
    } catch {}
    if ($actions.Count) { Log ("actions: " + ($actions -join ' | ')) }
}

Log "cc_watchdog started (tick=${TickSeconds}s, stall=$StallTicks ticks)"
while ($true) {
    try { Tick } catch { Log "TICK EXCEPTION: $_" }
    Start-Sleep -Seconds $TickSeconds
}
