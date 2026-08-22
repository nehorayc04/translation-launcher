#!/bin/bash
# Deploy the CP2077 QA fleet to ALL 7 streams (vm vm2 vm3 vm4 vm5 laptop + local desktop). Each
# stream gets its own DISJOINT balanced slice (splits/cpqa7_<name>.json, made by cpqa_reslice.py) and
# its OWN NIM key. cpqa_nim.py is launched WINDOWLESS (no popup); out.json is KEPT on re-deploy
# (resumable). NON-DESTRUCTIVE: only a prior cpqa_nim is killed+relaunched — any w3_nim/pt_nim keeps
# running (serial share; they idle as they drain, cpqa gets the cycles). Global progress is protected
# by the monotonic merge in pull_cpqa.sh, so reslicing loses nothing.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077/fleet"
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=5"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
VBS="$FLEET/hidden.vbs"

# streams temporarily freed for OTHER translation work (fleet/paused_streams) are NOT (re)deployed,
# so a deploy/reslice never drags a paused VM back onto CP2077 QA.
PAUSED=" $(cat "$FLEET/paused_streams" 2>/dev/null | tr '\n' ' ') "

deploy(){ # name host port user slice py wdir(back) wdirF(fwd) keysrc(back)
  local n=$1 h=$2 p=$3 u=$4 slice=$5 py=$6 wb=$7 wf=$8 ks=$9
  echo "--- $n ($h:$p) ---"
  case "$PAUSED" in *" $n "*) echo "  PAUSED (freed for other work) — skipped"; return 0 ;; esac
  if ! ssh $SSHO -p "$p" "$u@$h" "echo UP" >/dev/null 2>&1; then echo "  UNREACHABLE — skipped"; return 1; fi
  # 1. make dir + copy this stream's own key into it
  ssh $SSHO -p "$p" "$u@$h" "cmd /c \"if not exist \"$wb\" mkdir \"$wb\" & copy /y \"$ks\" \"$wb\\key.txt\" >nul & echo READY\"" 2>/dev/null | tr -d '\r'
  # 2. push worker + this stream's disjoint corpus slice
  scp $SSHO -P "$p" "$FLEET/cpqa_nim.py" "$u@$h:$wf/cpqa_nim.py" 2>/dev/null || { echo "  scp worker FAILED"; return 1; }
  scp $SSHO -P "$p" "$FLEET/splits/$slice" "$u@$h:$wf/corpus.json" 2>/dev/null || { echo "  scp corpus FAILED"; return 1; }
  # 3. kill ONLY a prior cpqa_nim (leave w3_nim/pt_nim alone), optionally RESET out.json (fresh
  #    review from 0 with the new corpus/worker), relaunch windowless
  local rmcmd=""
  [ "${RESET:-0}" = "1" ] && rmcmd="Remove-Item -Force -ErrorAction SilentlyContinue '$wb\\out.json','$wb\\cpqa.lock';"
  local pid
  pid=$(ssh $SSHO -p "$p" "$u@$h" "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'cpqa_nim'} | %{Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue}; Start-Sleep 2; $rmcmd (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$py -u $wb\\cpqa_nim.py'; CurrentDirectory='$wb'}).ProcessId\"" 2>/dev/null | tr -d '\r' | tr -d ' ')
  echo "  deployed $slice + launched cpqa (pid=$pid)${RESET:+ [RESET]}"
}

deploy_local(){ # desktop: local worker dir, launched via hidden.vbs + run.bat
  local dw="$FLEET/desktop_worker"
  echo "--- desktop (local) ---"
  case "$PAUSED" in *" desktop "*) echo "  PAUSED — skipped"; return 0 ;; esac
  mkdir -p "$dw"
  cp -f "$FLEET/cpqa_nim.py" "$dw/cpqa_nim.py"
  cp -f "$FLEET/splits/cpqa7_desktop.json" "$dw/corpus.json"
  [ -f "$dw/key.txt" ] || cp -f "$FLEET/../../witcher3/fleet/desktop_worker/key.txt" "$dw/key.txt" 2>/dev/null
  [ "${RESET:-0}" = "1" ] && rm -f "$dw/out.json" "$dw/cpqa.lock"
  cat > "$dw/run.bat" <<RUN
@echo off
"$LPY" -u "%~dp0cpqa_nim.py" >> "C:\\tmp\\cpqa_desktop.log" 2>&1
RUN
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ?{\$_.CommandLine -match 'desktop_worker.*cpqa_nim|cpqa_nim.*desktop_worker'} | %{Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue}" 2>/dev/null
  local DRUN; DRUN="$(cygpath -w "$dw/run.bat")"
  powershell -NoProfile -Command "(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wscript.exe \"$(cygpath -w "$VBS")\" \"$DRUN\"'}).ProcessId" 2>/dev/null | tr -d '\r '
  echo "  desktop launched (cpqa7_desktop.json)"
}

deploy vm     127.0.0.1 2222 vboxuser      cpqa7_vm.json     "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy vm2    127.0.0.1 2223 vboxuser      cpqa7_vm2.json    "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy vm3    127.0.0.1 2224 vboxuser      cpqa7_vm3.json    "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy vm4    100.116.78.88 2225 vboxuser      cpqa7_vm4.json    "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy vm5    100.116.78.88 2226 vboxuser      cpqa7_vm5.json    "$VPY" 'C:\cp2077qa' 'C:/cp2077qa' 'C:\w3w\key.txt'
deploy laptop 100.116.78.88 22   Nehoray_Cohen cpqa7_laptop.json "$LPY" \
  'C:\Users\Nehoray_Cohen\Projects\cp2077qa_worker' 'C:/Users/Nehoray_Cohen/Projects/cp2077qa_worker' \
  'C:\Users\Nehoray_Cohen\Projects\pt_laptop_worker\key.txt'
deploy_local
echo "=== cpqa 7-stream deploy done ==="
