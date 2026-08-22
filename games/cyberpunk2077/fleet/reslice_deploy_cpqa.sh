#!/bin/bash
# Redeploy the 4-way reslice (undone corpus) to the 4 CP2077 QA streams: vm(VM1) + vm2(VM2) +
# vm4 + laptop. Creates the work dir + copies each stream's OWN unique NIM key into it, pushes
# corpus.json + worker, relaunches cpqa_nim WINDOWLESS. out.json is KEPT (resumable).
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077/fleet"
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=8"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

PAUSED=" $(cat "$FLEET/paused_streams" 2>/dev/null | tr '\n' ' ') "  # never revive a freed stream

deploy(){ # name host port user slice py wdir(back) wdirF(fwd) keysrc(back)
  local n=$1 h=$2 p=$3 u=$4 slice=$5 py=$6 wb=$7 wf=$8 ks=$9
  echo "--- $n ($h:$p) $slice ---"
  case "$PAUSED" in *" $n "*) echo "  PAUSED (freed for other work) — skipped"; return 0 ;; esac
  ssh $SSHO -p "$p" "$u@$h" "cmd /c \"if not exist \"$wb\" mkdir \"$wb\" & copy /y \"$ks\" \"$wb\\key.txt\" >nul & echo READY\"" 2>/dev/null | tr -d '\r' | grep -viE 'warning|quantum|vulnerable|upgraded|openssh'
  scp $SSHO -P "$p" "$FLEET/cpqa_nim.py" "$u@$h:$wf/cpqa_nim.py" 2>/dev/null || { echo "  scp worker FAILED"; return 1; }
  scp $SSHO -P "$p" "$FLEET/splits/$slice" "$u@$h:$wf/corpus.json" 2>/dev/null || { echo "  scp corpus FAILED"; return 1; }
  local pid
  pid=$(ssh $SSHO -p "$p" "$u@$h" "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'cpqa_nim'} | %{Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue}; Start-Sleep 2; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$py -u $wb\\cpqa_nim.py'; CurrentDirectory='$wb'}).ProcessId\"" 2>/dev/null | tr -d '\r' | tr -d ' ')
  echo "  redeployed $slice + relaunched cpqa (pid=$pid)"
}

deploy vm     127.0.0.1 2222 vboxuser      reslice_0.json "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy vm2    127.0.0.1 2223 vboxuser      reslice_1.json "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy vm4    100.116.78.88 2225 vboxuser      reslice_2.json "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\ptw\key.txt'
deploy laptop 100.116.78.88 22   Nehoray_Cohen reslice_3.json "$LPY" \
  'C:\Users\Nehoray_Cohen\Projects\cp2077qa_worker' 'C:/Users/Nehoray_Cohen/Projects/cp2077qa_worker' \
  'C:\Users\Nehoray_Cohen\Projects\pt_laptop_worker\key.txt'
echo "=== cpqa 4-stream reslice deploy done (vm + vm2 + vm4 + laptop) ==="
