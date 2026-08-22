# Skyrim fleet watchdog -- runs every 5 min, hidden, no popups.
#
# It exists because every failure that has actually stalled this fleet is one a script can see
# and fix, and none of them announce themselves:
#   1. a HUNG GUEST. VBoxManage reports "running" while the guest answers no ssh at all, so a
#      hypervisor state check is NOT a liveness check -- probe the GUEST, and only power-cycle
#      after N consecutive failures so a booting/loaded VM is never killed. (vm3 and vm2 both
#      hit this on 2026-08-07.)
#   2. RETIRED-FLEET ZOMBIES. rdr2_nim/cc_nim workers left running after their game finished
#      keep spending the SAME groq/sambanova/nim keys, and the only symptom is more 429s and
#      timeouts on the game you care about (18 of them were found alive on 2026-08-07).
#   3. a DEAD or MISSING worker: fewer than 3 skyrim_nim on a machine.
#   4. a DISABLED launch task -- SkyrimMP was found Disabled on the desktop, which silently
#      removes the 5-minute self-heal everything else depends on.
#
# It deliberately does NOT judge "slow": productivity is the pull's job (it auto-reslices), and
# a stream that is merely throttled must never be killed.
$ErrorActionPreference = 'SilentlyContinue'
$FLEET     = 'C:\Users\Nehoray_Cohen\Projects\Game translator\games\skyrim\fleet'
$StatePath = Join-Path $FLEET '.watchdog_state.json'
$LogPath   = 'C:\tmp\skyrim_watchdog.log'
$VBox      = 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
$SshExe    = 'C:\WINDOWS\System32\OpenSSH\ssh.exe'
$KeyFile   = "$env:USERPROFILE\.ssh\id_ed25519"
# 🔴🔴 A HARDCODED KILL-LIST OF OTHER GAMES' WORKERS IS A TIME BOMB — 2026-08-07.
# This list was written while Skyrim was the LIVE fleet and rdr2/cc/pt/w3/ac2/cpqa were
# retired, so killing them was correct housekeeping. The roles then swapped: Skyrim finished,
# RDR2 became the live 21-stream run — and this watchdog spent the night EXECUTING THE ACTIVE
# FLEET on all seven machines every few minutes. It leaves no traceback (a Stop-Process is not
# an exception), the workers' own logs simply stop mid-pass, and the symptom is a throughput
# ceiling indistinguishable from provider throttling. It cost hours of misdiagnosis — the
# batch budget, the launcher, the job object and the provider quotas were all investigated
# first because every one of them produces the same silent stall.
# RULE: a janitor may only ever kill ITS OWN workers. `rdr2_nim` is REMOVED for exactly that
# reason; never re-add another game's worker name here. If a retired fleet really must be
# swept, do it once by hand, not from a recurring task that outlives the project it belonged to.
$ZOMBIE    = 'skyrim_nim_ZOMBIE_PLACEHOLDER_never_matches'
$STRIKES_BEFORE_POWERCYCLE = 3     # ~15 min of total silence before a destructive action

# ⚠️ PowerShell variable names are CASE-INSENSITIVE: $STATE and $state are the SAME variable.
# A path named like its data silently gets overwritten and the state file is never written
# (this bit the earlier VM watchdog). Hence $StatePath / $state, deliberately distinct.
$state = @{}
if (Test-Path $StatePath) {
  try { (Get-Content $StatePath -Raw | ConvertFrom-Json).PSObject.Properties |
          ForEach-Object { $state[$_.Name] = [int]$_.Value } } catch {}
}

function Say($m) {
  # ⚠️ Use DateTimeOffset, not `Get-Date -UFormat %s`: under Windows PowerShell 5.1 + he-IL
  # that returns a comma-decimal string that [double]::Parse throws on, and with
  # SilentlyContinue the whole tick then skips in total silence.
  $t = [DateTimeOffset]::UtcNow.ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss')
  Add-Content -Path $LogPath -Value "$t  $m"
}

# 🔴 ONLY THE MACHINES THIS GAME OWNS. Two games now share the 7 boxes, and this watchdog
# relaunches its game's task whenever it sees fewer than 3 workers -- pointed at a machine that
# moved to the OTHER game, it would resurrect the fleet that left, on that machine's key set,
# with no error anywhere. Keep this list in step with games/skyrim/fleet/machines.json.
$machines = @(
  @{ n='desktop'; local=$true;  dir='C:\skyrimw' }
)

# The remote half is one base64 script: fighting ssh quoting is how these checks end up
# silently doing nothing (a bare `dir C:\x` over ssh loses its argument entirely).
$remote = @"
`$ErrorActionPreference='SilentlyContinue'
`$z=0
Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { `$_.CommandLine -match '$ZOMBIE' } | ForEach-Object { try { Stop-Process -Id `$_.ProcessId -Force; `$z++ } catch {} }
`$w=@(Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { `$_.CommandLine -match 'skyrim_nim' }).Count
`$t=0
Get-ScheduledTask | Where-Object { `$_.TaskName -match '^Skyrim' -and `$_.State -eq 'Disabled' } | ForEach-Object { Enable-ScheduledTask -TaskName `$_.TaskName | Out-Null; `$t++ }
if (`$w -lt 3) { schtasks /run /tn SkyrimMP | Out-Null }
Write-Output "OK z=`$z w=`$w t=`$t"
"@
$enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($remote))

foreach ($m in $machines) {
  $name = $m.n
  if ($m.local) {
    $out = powershell -NoProfile -EncodedCommand $enc 2>&1 | Select-String '^OK' | Select-Object -First 1
  } else {
    $out = & $SshExe -i $KeyFile -o StrictHostKeyChecking=no -o BatchMode=yes `
                     -o ConnectTimeout=45 -p $m.port "$($m.user)@$($m.host)" `
                     "powershell -NoProfile -EncodedCommand $enc" 2>&1 |
           Select-String '^OK' | Select-Object -First 1
  }

  if ($out) {
    if ($state[$name] -gt 0) { Say "$name recovered (was $($state[$name]) strike(s))" }
    $state[$name] = 0
    $s = "$out"
    if ($s -notmatch 'z=0 ' -or $s -notmatch ' t=0') { Say "$name $s" }
    if ($s -match 'w=(\d+)' -and [int]$Matches[1] -lt 3) { Say "$name only $($Matches[1])/3 workers -> SkyrimMP triggered" }
    continue
  }

  # no answer at all
  $state[$name] = [int]$state[$name] + 1
  Say "$name UNREACHABLE (strike $($state[$name])/$STRIKES_BEFORE_POWERCYCLE)"
  if ($state[$name] -ge $STRIKES_BEFORE_POWERCYCLE -and $m.vbox) {
    # A hard poweroff can NUL-truncate whatever the guest was writing; that is survivable here
    # because the worker moves an unreadable bank aside and the pull validates before replacing
    # the local copy -- but it is exactly why this needs 3 strikes, not 1.
    Say "$name power-cycling '$($m.vbox)'"
    & $VBox controlvm $m.vbox poweroff  | Out-Null
    Start-Sleep -Seconds 8
    & $VBox startvm  $m.vbox --type headless | Out-Null
    $state[$name] = 0
  }
}

# keep the pull + the site pusher alive (they are what the dashboard and the website read)
if (-not (Get-ScheduledTask -TaskName 'SkyrimFleetPull' | Where-Object { $_.State -ne 'Disabled' })) {
  Enable-ScheduledTask -TaskName 'SkyrimFleetPull' | Out-Null; Say 'SkyrimFleetPull re-enabled'
}
$push = @(Get-CimInstance Win32_Process -Filter "name='python.exe'" |
          Where-Object { $_.CommandLine -match 'skyrim_progress' })
if ($push.Count -eq 0) {
  Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine    = '"C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u skyrim_progress.py'
    CurrentDirectory = $FLEET } | Out-Null
  Say 'site pusher restarted'
} elseif ($push.Count -gt 1) {
  # two pushers double-sample the history and publish a FALSE 0/h on a healthy fleet
  $push | Sort-Object CreationDate | Select-Object -Skip 1 |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  Say "killed $($push.Count - 1) duplicate pusher(s)"
}

$state | ConvertTo-Json -Compress | Set-Content -Path $StatePath -Encoding UTF8
