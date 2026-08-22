#!/bin/bash
# Deploy the 6 disjoint reslice_<n>.json as each stream's new corpus.json + relaunch. out.json KEPT.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

relaunch_ps(){ # host port user py wdir(backslash)
  local h=$1 p=$2 u=$3 py=$4 wdir=$5
  ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$u@$h" \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'w3_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 2; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$py -u $wdir\\w3_nim.py'; CurrentDirectory='$wdir'}).ProcessId\"" 2>/dev/null | tr -d '\r'
}

push_remote(){ # name host port user sdir(fwd) py wdir(back)
  local n=$1 h=$2 p=$3 u=$4 sdir=$5 py=$6 wdir=$7
  echo "--- $n ($h:$p) ---"
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$FLEET/reslice_$n.json" "$u@$h:$sdir/corpus.json" 2>/dev/null \
    || { echo "  scp FAILED — skip (heal/W3Worker will keep old corpus running)"; return; }
  local pid=$(relaunch_ps "$h" "$p" "$u" "$py" "$wdir")
  echo "  pushed slice + relaunched (pid=$pid)"
}

push_remote vm     127.0.0.1 2222 vboxuser      'C:/w3w' "$VPY" 'C:\w3w'
push_remote vm2    127.0.0.1 2223 vboxuser      'C:/w3w' "$VPY" 'C:\w3w'
push_remote vm4    10.0.0.49 2225 vboxuser      'C:/w3w' "$VPY" 'C:\w3w'
push_remote vm5    10.0.0.49 2226 vboxuser      'C:/w3w' "$VPY" 'C:\w3w'
push_remote laptop 10.0.0.49 22   Nehoray_Cohen 'C:/Users/Nehoray_Cohen/Projects/w3_laptop_worker' "$LPY" 'C:\Users\Nehoray_Cohen\Projects\w3_laptop_worker'

# desktop (LOCAL) — swap corpus + relaunch HIDDEN
echo "--- desktop (local) ---"
DW="$FLEET/desktop_worker"
cp "$FLEET/reslice_desktop.json" "$DW/corpus.json"
VBS='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\hidden.vbs'
DRUN='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\desktop_worker\run.bat'
DCWD='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\desktop_worker'
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ?{\$_.CommandLine -match 'desktop_worker'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 2; Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wscript.exe \"$VBS\" \"$DRUN\"'; CurrentDirectory='$DCWD'} | Out-Null" 2>/dev/null
echo "  desktop slice swapped + relaunched hidden"
echo "=== reslice deploy done ==="
