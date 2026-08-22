#!/bin/bash
# Deploy the gender-review worker to the FREE streams (vm, vm2 remote + desktop local) and launch it.
# Remote worker dir = C:\ptwg (separate from C:\ptw so it never touches the PT translation worker).
set -u
KEY=~/.ssh/id_ed25519
HERE="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet/gender"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

deploy_vm(){ # name port
  local n=$1 p=$2
  echo "--- $n (127.0.0.1:$p) ---"
  [ -s "$HERE/gslice_$n.json" ] || { echo "  no gslice_$n.json — skip"; return; }
  ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 vboxuser@127.0.0.1 \
    "if not exist C:\\ptwg mkdir C:\\ptwg & copy /Y C:\\ptw\\key.txt C:\\ptwg\\key.txt >NUL & del /Q C:\\ptwg\\out.json 2>NUL" 2>/dev/null
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HERE/pt_gender_nim.py" "vboxuser@127.0.0.1:C:/ptwg/pt_gender_nim.py" 2>/dev/null || { echo "  scp worker FAILED"; return; }
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HERE/gslice_$n.json" "vboxuser@127.0.0.1:C:/ptwg/corpus.json" 2>/dev/null || { echo "  scp corpus FAILED"; return; }
  local pid=$(ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 vboxuser@127.0.0.1 \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'pt_gender_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 1; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$VPY -u C:\\ptwg\\pt_gender_nim.py'; CurrentDirectory='C:\\ptwg'}).ProcessId\"" 2>/dev/null | tr -d '\r' | tail -1)
  echo "  deployed + launched (pid=$pid)"
}

deploy_vm vm  2222
deploy_vm vm2 2223

# desktop = LOCAL
echo "--- desktop (local) ---"
if [ -s "$HERE/gslice_desktop.json" ]; then
  mkdir -p "$HERE/desktop"
  cp -f "$HERE/pt_gender_nim.py" "$HERE/desktop/pt_gender_nim.py"
  cp -f "$HERE/gslice_desktop.json" "$HERE/desktop/corpus.json"
  cp -f "$HERE/../desktop_worker/key.txt" "$HERE/desktop/key.txt"
  rm -f "$HERE/desktop/out.json"
  DWIN="$(cygpath -w "$HERE/desktop")"
  powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ?{\$_.CommandLine -match 'gender.desktop.pt_gender_nim|ptwg'} | %{Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue}; Start-Process -WindowStyle Hidden -FilePath '$LPY' -ArgumentList '-u','$DWIN\\pt_gender_nim.py' -WorkingDirectory '$DWIN'" 2>/dev/null
  echo "  desktop launched (local)"
else
  echo "  no gslice_desktop.json — skip"
fi
echo "=== gender deploy done ==="
