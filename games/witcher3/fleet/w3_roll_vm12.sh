#!/bin/bash
# Targeted gender-aware rollout for vm + vm2 (127.0.0.1:2222/2223) ONLY — after a wedged-VM reset.
# Waits for SSH to return, then pull→genderize→push→relaunch. Leaves vm4/vm5/laptop/desktop alone.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
AR="$FLEET/../extract/ar.json"; NIM="$FLEET/w3_nim.py"
TMP=/c/tmp/w3_roll; mkdir -p "$TMP"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'

genderize(){ "$PY" - "$1" "$AR" <<'PYEOF'
import json,sys
src,arf=sys.argv[1],sys.argv[2]
d=json.load(open(src,encoding='utf-8')); ar=json.load(open(arf,encoding='utf-8'))
out={k:{'en':(v.get('en') if isinstance(v,dict) else v),'ar':ar.get(k,'')} for k,v in d.items()}
json.dump(out,open(src,'w',encoding='utf-8'),ensure_ascii=False)
print(f'  genderized {len(out)} keys, {sum(1 for v in out.values() if v["ar"])} with Arabic')
PYEOF
}

wait_ssh(){ local p=$1 n=$2 i
  for i in $(seq 1 30); do
    if ssh -i "$KEY" -p "$p" vboxuser@127.0.0.1 -o StrictHostKeyChecking=no -o ConnectTimeout=8 -o BatchMode=yes "exit" 2>/dev/null; then
      echo "  $n SSH up (after ${i} tries)"; return 0; fi
    sleep 6
  done
  echo "  $n SSH still down after 3min — skip"; return 1
}

roll(){ local n=$1 p=$2
  echo "--- $n (127.0.0.1:$p) ---"
  wait_ssh "$p" "$n" || return
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "vboxuser@127.0.0.1:C:/w3w/corpus.json" "$TMP/$n.json" 2>/dev/null \
    || { echo "  scp pull FAILED"; return; }
  genderize "$TMP/$n.json" || return
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$TMP/$n.json" "vboxuser@127.0.0.1:C:/w3w/corpus.json" 2>/dev/null
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$NIM" "vboxuser@127.0.0.1:C:/w3w/w3_nim.py" 2>/dev/null
  ssh -i "$KEY" -p "$p" vboxuser@127.0.0.1 -o StrictHostKeyChecking=no -o ConnectTimeout=20 \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'w3_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 2; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$VPY -u C:\\w3w\\w3_nim.py'; CurrentDirectory='C:\\w3w'}).ProcessId\"" 2>/dev/null | tr -d '\r'
  echo "  $n relaunched gender-aware"
}

roll vm  2222
roll vm2 2223
echo "=== vm/vm2 rollout done ==="
