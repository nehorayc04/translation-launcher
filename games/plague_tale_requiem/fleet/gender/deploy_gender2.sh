#!/bin/bash
# Deploy the gender-review worker to vm3 + vm4 + vm5 + laptop (vm3 via localhost; vm4/vm5/laptop via
# Tailscale 100.116.78.88). Separate worker dir (C:\ptwg on VMs, C:\Users\Nehoray_Cohen\ptwg on laptop)
# so it never touches the PT-translation worker. Keys copied from each stream's PT worker key.txt.
set -u
KEY=~/.ssh/id_ed25519
HERE="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet/gender"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
sshx(){ ssh -i "$KEY" -p "$2" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$1@$3" "$4" 2>/dev/null; }

deploy(){ # name host port user pydirWin pydirFwd py keysrcWin
  local n=$1 host=$2 port=$3 user=$4 dw=$5 df=$6 py=$7 ksrc=$8
  echo "--- $n ($user@$host:$port -> $dw) ---"
  [ -s "$HERE/gslice_$n.json" ] || { echo "  no gslice_$n.json — skip"; return; }
  sshx "$user" "$port" "$host" "if not exist $dw mkdir $dw & copy /Y $ksrc $dw\\key.txt >NUL & del /Q $dw\\out.json 2>NUL"
  scp -i "$KEY" -P "$port" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HERE/pt_gender_nim.py" "$user@$host:$df/pt_gender_nim.py" 2>/dev/null || { echo "  scp worker FAILED"; return; }
  scp -i "$KEY" -P "$port" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HERE/gslice_$n.json" "$user@$host:$df/corpus.json" 2>/dev/null || { echo "  scp corpus FAILED"; return; }
  local pid=$(sshx "$user" "$port" "$host" "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'ptwg.*pt_gender_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 1; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$py -u $dw\\pt_gender_nim.py'; CurrentDirectory='$dw'}).ProcessId\"" | tr -d '\r' | tail -1)
  echo "  deployed + launched (pid=$pid)"
}

deploy vm3    127.0.0.1     2224 vboxuser      'C:\ptwg'                          'C:/ptwg'                          "$VPY" 'C:\ptw\key.txt'
deploy vm4    100.116.78.88 2225 vboxuser      'C:\ptwg'                          'C:/ptwg'                          "$VPY" 'C:\ptw\key.txt'
deploy vm5    100.116.78.88 2226 vboxuser      'C:\ptwg'                          'C:/ptwg'                          "$VPY" 'C:\ptw\key.txt'
deploy laptop 100.116.78.88 22   Nehoray_Cohen 'C:\Users\Nehoray_Cohen\ptwg'      'C:/Users/Nehoray_Cohen/ptwg'      "$LPY" 'C:\Users\Nehoray_Cohen\Projects\pt_laptop_worker\key.txt'
echo "=== gender deploy2 done (vm3 vm4 vm5 laptop) ==="
