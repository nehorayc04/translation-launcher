#!/bin/bash
# OS-level autonomous fleet monitor — runs independently of the Claude session.
# Every 10 min: (1) heal any DEAD remote worker via CIM relaunch, (2) log spine% + pull-freshness.
# Log: /c/tmp/fleet_monitor.log  (read it any time to see the last state).
KEY=~/.ssh/id_ed25519
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
CP="/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077"
LOG=/c/tmp/fleet_monitor.log
SSHO="-o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15"
# name host port user relaunch_cmd cwd
heal() {  # $1 name $2 host $3 port $4 user $5 pyexe $6 script $7 cwd
  local cnt
  cnt=$(ssh -i "$KEY" -p "$3" $SSHO "$4@$2" "powershell -NoProfile -Command \"(Get-Process python* -ErrorAction SilentlyContinue).Count\"" 2>/dev/null | tr -d '\r')
  if [ "${cnt:-0}" = "0" ] || [ -z "$cnt" ]; then
    ssh -i "$KEY" -p "$3" $SSHO "$4@$2" "powershell -NoProfile -Command \"Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$5 -u $6'; CurrentDirectory='$7'}\"" 2>/dev/null >/dev/null
    echo "$(date +%H:%M:%S) HEAL $1 (was down) -> relaunched" >> "$LOG"
  fi
}
echo "$(date +%H:%M:%S) === fleet_monitor start (pid $$) ===" >> "$LOG"
while true; do
  heal vm     127.0.0.1 2222 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
  heal vm2    127.0.0.1 2223 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
  heal vm4    10.0.0.49 2225 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
  heal vm5    10.0.0.49 2226 vboxuser      'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe' 'C:\vmw\vm_nim.py' 'C:\vmw'
  heal laptop 10.0.0.49 22   Nehoray_Cohen 'C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe' 'laptop_nim.py' 'C:\Users\Nehoray_Cohen\Projects\cp2077_laptop_worker'
  sp=$(timeout 50 "$PY" "$CP/nim_watchdog.py" --status 2>/dev/null | tail -1)
  pl=$(tail -1 /c/tmp/pull_banks.log 2>/dev/null)
  echo "$(date +%H:%M:%S) $sp | lastpull: $pl" >> "$LOG"
  sleep 600
done
