#!/bin/bash
# Deploy the reslice_<n>.json as each ACTIVE stream's new corpus.json + relaunch pt_nim. out.json KEPT.
# Only the 4 streams NOT on the W3 loan: vm3 vm4 vm5 laptop. desktop/vm/vm2 are intentionally untouched.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

relaunch_ps(){ # host port user py wdir(backslash)
  local h=$1 p=$2 u=$3 py=$4 wdir=$5
  ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$u@$h" \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'pt_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 2; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$py -u $wdir\\pt_nim.py'; CurrentDirectory='$wdir'}).ProcessId\"" 2>/dev/null | tr -d '\r'
}

push_remote(){ # name host port user sdir(fwd) py wdir(back)
  local n=$1 h=$2 p=$3 u=$4 sdir=$5 py=$6 wdir=$7
  echo "--- $n ($h:$p) ---"
  [ -s "$FLEET/reslice_$n.json" ] || { echo "  no reslice_$n.json — skip"; return; }
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$FLEET/reslice_$n.json" "$u@$h:$sdir/corpus.json" 2>/dev/null \
    || { echo "  scp FAILED — skip (heal/PTWorker keeps the old corpus running)"; return; }
  cp -f "$FLEET/reslice_$n.json" "$FLEET/splits/corpus_pt_$n.json"   # keep the repo record in sync
  local pid=$(relaunch_ps "$h" "$p" "$u" "$py" "$wdir")
  echo "  pushed slice + relaunched (pid=$pid)"
}

push_remote vm3    127.0.0.1 2224 vboxuser      'C:/ptw' "$VPY" 'C:\ptw'
push_remote vm4    100.116.78.88 2225 vboxuser      'C:/ptw' "$VPY" 'C:\ptw'
push_remote vm5    100.116.78.88 2226 vboxuser      'C:/ptw' "$VPY" 'C:\ptw'
push_remote laptop 100.116.78.88 22   Nehoray_Cohen 'C:/Users/Nehoray_Cohen/Projects/pt_laptop_worker' "$LPY" 'C:\Users\Nehoray_Cohen\Projects\pt_laptop_worker'

echo "=== PT reslice deploy done (4 active streams: vm3 vm4 vm5 laptop) ==="
