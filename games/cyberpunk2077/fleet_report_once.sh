#!/bin/bash
# One-shot fleet heal + Hebrew report. Registered in Windows Task Scheduler to run every 10 min,
# so it fires INDEPENDENT of any Claude chat session (this is what actually gave hourly autonomy).
# Appends a timestamped report to /c/tmp/fleet_report.txt (open it any time / Get-Content -Wait).
KEY=~/.ssh/id_ed25519
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
CP="/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077"
REP=/c/tmp/fleet_report.txt
SSHO="-o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15"
alive=0; healed=""
check() {  # name host port user pyexe script cwd
  local cnt
  cnt=$(ssh -i "$KEY" -p "$3" $SSHO "$4@$2" "powershell -NoProfile -Command \"(Get-Process python* -ErrorAction SilentlyContinue).Count\"" 2>/dev/null | tr -d '\r')
  if [ "${cnt:-0}" = "0" ] || [ -z "$cnt" ]; then
    ssh -i "$KEY" -p "$3" $SSHO "$4@$2" "powershell -NoProfile -Command \"Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$5 -u $6'; CurrentDirectory='$7'}\"" 2>/dev/null >/dev/null
    healed="$healed $1"
  else
    alive=$((alive+1))
  fi
}
check vm     127.0.0.1 2222 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
check vm2    127.0.0.1 2223 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
check vm4    10.0.0.49 2225 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
check vm5    10.0.0.49 2226 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
check laptop 10.0.0.49 22   Nehoray_Cohen 'C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe' 'laptop_nim.py' 'C:\Users\Nehoray_Cohen\Projects\cp2077_laptop_worker'
sp=$(timeout 50 "$PY" "$CP/nim_watchdog.py" --status 2>/dev/null | tail -1)
pl=$(tail -1 /c/tmp/pull_banks.log 2>/dev/null)
{
  echo "──────── $(date '+%Y-%m-%d %H:%M:%S') ────────"
  echo "streams חיים: $alive/5${healed:+  | רופאו:$healed}"
  echo "spine: $sp"
  echo "pull אחרון: $pl"
} >> "$REP"
