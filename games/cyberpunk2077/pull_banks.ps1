# pull_banks.ps1 — recurring pull of each VM/laptop NIM stream's out.json into its host bank.
# Launched detached via Win32_Process.Create so it survives the launching shell.
# Atomic per-file (scp to .tmp then Move-Item) so the watchdog never reads a half-written bank.
$key  = "$env:USERPROFILE\.ssh\id_ed25519"
$bank = "C:\Users\Nehoray_Cohen\Projects\Game translator\games\cyberpunk2077\agent_handoff_qa"
$log  = "C:\tmp\pull_banks.log"
$streams = @(
  @{ n='vm';     host='127.0.0.1'; port=2222; user='vboxuser';      path='C:/vmw/out.json' },
  @{ n='vm2';    host='127.0.0.1'; port=2223; user='vboxuser';      path='C:/vmw/out.json' },
  @{ n='vm4';    host='10.0.0.49'; port=2225; user='vboxuser';      path='C:/vmw/out.json' },
  @{ n='vm5';    host='10.0.0.49'; port=2226; user='vboxuser';      path='C:/vmw/out.json' },
  @{ n='laptop'; host='10.0.0.49'; port=22;   user='Nehoray_Cohen'; path='C:/Users/Nehoray_Cohen/Projects/cp2077_laptop_worker/out.json' }
)
function Log($m) { "$([DateTime]::Now.ToString('HH:mm:ss')) $m" | Out-File -Append -Encoding utf8 $log }
Log "pull_banks started (pid $PID)"
while ($true) {
  foreach ($s in $streams) {
    $dest = "$bank\retrans_agent_$($s.n)\retrans_corrections.json"
    $tmp  = "$dest.pull.tmp"
    if (-not (Test-Path (Split-Path $dest))) { continue }
    Remove-Item $tmp -ErrorAction SilentlyContinue
    & scp -i $key -P $s.port -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o BatchMode=yes -o ServerAliveInterval=10 "$($s.user)@$($s.host):$($s.path)" $tmp 2>$null
    if ((Test-Path $tmp) -and ((Get-Item $tmp).Length -gt 2)) {
      try {
        $null = Get-Content $tmp -Raw | ConvertFrom-Json   # only replace if valid JSON
        Move-Item -Force $tmp $dest
        $cnt = ((Get-Content $dest -Raw | ConvertFrom-Json).PSObject.Properties).Count
        Log "$($s.n): pulled ($cnt entries)"
      } catch { Log "$($s.n): bad json, skipped"; Remove-Item $tmp -ErrorAction SilentlyContinue }
    } else { Remove-Item $tmp -ErrorAction SilentlyContinue; Log "$($s.n): unreachable" }
  }
  Start-Sleep -Seconds 180
}
