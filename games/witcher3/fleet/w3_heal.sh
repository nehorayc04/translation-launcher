#!/bin/bash
# W3 fleet self-heal: if a stream's w3_nim.py isn't running, CIM-relaunch it. Durable OS task (10 min).
KEY=~/.ssh/id_ed25519
LOG=/c/tmp/w3_heal.log
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
heal_vm(){ local n=$1 h=$2 p=$3
  local alive=$(ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 vboxuser@$h "powershell -NoProfile -Command \"(Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'w3_nim'}).ProcessId\"" 2>/dev/null | tr -d '\r')
  if [ -z "$alive" ]; then
    ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 vboxuser@$h "powershell -NoProfile -Command \"(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$VPY -u C:\w3w\w3_nim.py'; CurrentDirectory='C:\w3w'}).ProcessId\"" 2>/dev/null | tr -d '\r'
    echo "$(date +%H:%M:%S) HEALED $n" >> "$LOG"
  fi
}
heal_vm vm  127.0.0.1 2222
heal_vm vm2 127.0.0.1 2223
heal_vm vm4 10.0.0.49 2225
heal_vm vm5 10.0.0.49 2226
# laptop
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
LW3='C:\Users\Nehoray_Cohen\Projects\w3_laptop_worker'
la=$(ssh -i "$KEY" -p 22 -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 Nehoray_Cohen@10.0.0.49 "powershell -NoProfile -Command \"(Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'w3_nim'}).ProcessId\"" 2>/dev/null | tr -d '\r')
if [ -z "$la" ]; then
  ssh -i "$KEY" -p 22 -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 Nehoray_Cohen@10.0.0.49 "powershell -NoProfile -Command \"(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$LPY -u $LW3\w3_nim.py'; CurrentDirectory='$LW3'}).ProcessId\"" 2>/dev/null | tr -d '\r'
  echo "$(date +%H:%M:%S) HEALED laptop" >> "$LOG"
fi
# desktop (LOCAL) 6th stream — relaunch HIDDEN (wscript hidden.vbs) if no python is running desktop_worker
VBS='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\hidden.vbs'
DRUN='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\desktop_worker\run.bat'
DCWD='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\desktop_worker'
da=$(MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {\$_.CommandLine -match 'desktop_worker'}).ProcessId" 2>/dev/null | tr -d '\r' | tr -d ' ')
if [ -z "$da" ]; then
  MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wscript.exe \"$VBS\" \"$DRUN\"'; CurrentDirectory='$DCWD'} | Out-Null" 2>/dev/null
  echo "$(date +%H:%M:%S) HEALED desktop" >> "$LOG"
fi
# W3 progress pusher (LOCAL) — relaunch if not running
PRUN='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\run_progress.bat'
PCWD='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet'
pa=$(MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {\$_.CommandLine -match 'w3_progress'}).ProcessId" 2>/dev/null | tr -d '\r' | tr -d ' ')
if [ -z "$pa" ]; then
  MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wscript.exe \"$VBS\" \"$PRUN\"'; CurrentDirectory='$PCWD'} | Out-Null" 2>/dev/null
  echo "$(date +%H:%M:%S) HEALED progress" >> "$LOG"
fi
