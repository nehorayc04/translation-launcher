#!/bin/bash
# Deploy PT gender-review to ALL 7 streams. 6 SSH (vm vm2 vm3 vm4 vm5 laptop) launched via a robust
# per-stream run_gender.bat (PYTHONIOENCODING=utf-8 + file redirect so a detached no-console worker
# never dies on a print). desktop = local, run by the PTGenderDesk scheduled task. out.json PRESERVED
# on streams that already have one (their reviewed keys stay in the banks); slices are the REMAINING set.
set -u
KEY=~/.ssh/id_ed25519
HERE="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet/gender"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
TMP="$HERE/_bats"; mkdir -p "$TMP"
sshx(){ ssh -i "$KEY" -p "$2" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$1@$3" "$4" 2>/dev/null; }

mkbat(){ # py dwWin -> stdout .bat content (CRLF added by caller)
  printf '@echo off\r\nset PYTHONIOENCODING=utf-8\r\n"%s" -u "%s\\pt_gender_nim.py" > "%s\\worker.log" 2>&1\r\n' "$1" "$2" "$2"
}

deploy(){ # name host port user dwWin dwFwd py keysrcWin
  local n=$1 host=$2 port=$3 user=$4 dw=$5 df=$6 py=$7 ksrc=$8
  echo "--- $n ($user@$host:$port) ---"
  [ -s "$HERE/gslice_$n.json" ] || { echo "  no gslice_$n.json — skip"; return; }
  sshx "$user" "$port" "$host" "if not exist $dw mkdir $dw & copy /Y $ksrc $dw\\key.txt >NUL"
  mkbat "$py" "$dw" > "$TMP/run_gender_$n.bat"
  scp -i "$KEY" -P "$port" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HERE/pt_gender_nim.py" "$user@$host:$df/pt_gender_nim.py" 2>/dev/null || { echo "  scp worker FAILED"; return; }
  scp -i "$KEY" -P "$port" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HERE/gslice_$n.json" "$user@$host:$df/corpus.json" 2>/dev/null || { echo "  scp corpus FAILED"; return; }
  scp -i "$KEY" -P "$port" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$TMP/run_gender_$n.bat" "$user@$host:$df/run_gender.bat" 2>/dev/null || { echo "  scp bat FAILED"; return; }
  local pid=$(sshx "$user" "$port" "$host" "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'ptwg.*pt_gender_nim|pt_gender_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 1; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='cmd /c $dw\\run_gender.bat'; CurrentDirectory='$dw'}).ProcessId\"" | tr -d '\r' | tail -1)
  echo "  deployed + launched (pid=$pid)"
}

deploy vm     127.0.0.1     2222 vboxuser      'C:\ptwg'                     'C:/ptwg'                     "$VPY" 'C:\ptw\key.txt'
deploy vm2    127.0.0.1     2223 vboxuser      'C:\ptwg'                     'C:/ptwg'                     "$VPY" 'C:\ptw\key.txt'
deploy vm3    127.0.0.1     2224 vboxuser      'C:\ptwg'                     'C:/ptwg'                     "$VPY" 'C:\ptw\key.txt'
deploy vm4    100.116.78.88 2225 vboxuser      'C:\ptwg'                     'C:/ptwg'                     "$VPY" 'C:\ptw\key.txt'
deploy vm5    100.116.78.88 2226 vboxuser      'C:\ptwg'                     'C:/ptwg'                     "$VPY" 'C:\ptw\key.txt'
deploy laptop 100.116.78.88 22   Nehoray_Cohen 'C:\Users\Nehoray_Cohen\ptwg' 'C:/Users/Nehoray_Cohen/ptwg' "$LPY" 'C:\Users\Nehoray_Cohen\Projects\pt_laptop_worker\key.txt'

# desktop = LOCAL: refresh files; PTGenderDesk scheduled task runs it (registered separately)
echo "--- desktop (local) ---"
if [ -s "$HERE/gslice_desktop.json" ]; then
  mkdir -p "$HERE/desktop"
  cp -f "$HERE/pt_gender_nim.py" "$HERE/desktop/pt_gender_nim.py"
  cp -f "$HERE/gslice_desktop.json" "$HERE/desktop/corpus.json"
  cp -f "$HERE/../desktop_worker/key.txt" "$HERE/desktop/key.txt"
  echo "  desktop files refreshed (PTGenderDesk task runs the worker)"
else
  echo "  no gslice_desktop.json — skip"
fi
echo "=== gender deploy_all done (7 streams) ==="
