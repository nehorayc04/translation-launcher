#!/bin/bash
# ONE gender-review tick (PTGenderPull task, ~3 min): relaunch a stream's worker ONLY if its
# worker.log heartbeat is STALE (>8 min) — reliable (file mtime), unlike process-enum which gives
# false negatives. The worker itself is a PID-singleton (newest wins), so a relaunch can never pile
# up duplicates. Then pull+merge all 7 (desktop healed by the PTGenderDesk task).
KEY=~/.ssh/id_ed25519
G="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet/gender"
sshx(){ timeout 30 ssh -i "$KEY" -p "$2" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=12 "$1@$3" "$4" 2>/dev/null | tr -d '\r'; }
age(){ sshx "$1" "$2" "$3" "powershell -NoProfile -Command \"if (Test-Path '$4\\worker.log') {[int]((Get-Date)-(Get-Item '$4\\worker.log').LastWriteTime).TotalSeconds} else {99999}\"" | grep -oE '^[0-9]+' | tail -1; }
launch(){ sshx "$1" "$2" "$3" "powershell -NoProfile -Command \"(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='cmd /c $4\\run_gender.bat'; CurrentDirectory='$4'}).ProcessId\"" >/dev/null; }
# name user host port dirWin
STREAMS=(
 "vm vboxuser 127.0.0.1 2222 C:\\ptwg"
 "vm2 vboxuser 127.0.0.1 2223 C:\\ptwg"
 "vm4 vboxuser 100.116.78.88 2225 C:\\ptwg"
 "laptop Nehoray_Cohen 100.116.78.88 22 C:\\Users\\Nehoray_Cohen\\ptwg"
)
for s in "${STREAMS[@]}"; do
  set -- $s; n=$1 u=$2 h=$3 p=$4 dw=$5
  a=$(age "$u" "$p" "$h" "$dw")
  # relaunch only on a CONFIRMED stale/absent heartbeat (empty read = unknown -> leave alone)
  if [ -n "$a" ] && [ "$a" -gt 480 ] 2>/dev/null; then launch "$u" "$p" "$h" "$dw"; fi
done
bash "$G/pull_gender2.sh" >/dev/null 2>&1
