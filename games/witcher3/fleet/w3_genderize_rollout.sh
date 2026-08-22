#!/bin/bash
# Convert the 5 REMOTE W3 streams to gender-aware in place: pull each remote's corpus.json,
# add the Arabic gender field per key (mapping-agnostic — preserves each remote's exact slice),
# push it back + the new gender-aware w3_nim.py, then kill+relaunch. out.json is KEPT (done keys
# skipped → zero re-translation). Idempotent (genderize is safe on an already-converted corpus).
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
AR="$FLEET/../extract/ar.json"
NIM="$FLEET/w3_nim.py"
TMP=/c/tmp/w3_roll; mkdir -p "$TMP"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

genderize(){ "$PY" - "$1" "$AR" <<'PYEOF'
import json,sys
src,arf=sys.argv[1],sys.argv[2]
d=json.load(open(src,encoding='utf-8')); ar=json.load(open(arf,encoding='utf-8'))
out={k:{'en':(v.get('en') if isinstance(v,dict) else v),'ar':ar.get(k,'')} for k,v in d.items()}
json.dump(out,open(src,'w',encoding='utf-8'),ensure_ascii=False)
print(f'genderized {len(out)} keys, {sum(1 for v in out.values() if v["ar"])} with Arabic')
PYEOF
}

roll_vm(){ # name host port sdir(fwd-slash for scp) wdir(backslash for powershell) py
  local n=$1 h=$2 p=$3 sdir=$4 wdir=$5 py=$6
  echo "--- $n ($h:$p) ---"
  # 1) pull corpus  (scp needs FORWARD-slash remote paths, like pull_w3.sh)
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "vboxuser@$h:$sdir/corpus.json" "$TMP/$n.json" 2>/dev/null \
    || { echo "  scp pull FAILED — skip"; return; }
  # 2) genderize locally
  genderize "$TMP/$n.json" || { echo "  genderize FAILED — skip"; return; }
  # 3) push corpus back + the new worker
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$TMP/$n.json" "vboxuser@$h:$sdir/corpus.json" 2>/dev/null
  scp -i "$KEY" -P "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$NIM" "vboxuser@$h:$sdir/w3_nim.py" 2>/dev/null
  # 4) kill old python + relaunch (powershell needs BACK-slash paths)
  ssh -i "$KEY" -p "$p" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "vboxuser@$h" \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'w3_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 2; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$py -u $wdir\\w3_nim.py'; CurrentDirectory='$wdir'}).ProcessId\"" 2>/dev/null | tr -d '\r'
  echo "  $n relaunched gender-aware"
}

roll_vm vm  127.0.0.1 2222 'C:/w3w' 'C:\w3w' "$VPY"
roll_vm vm2 127.0.0.1 2223 'C:/w3w' 'C:\w3w' "$VPY"
roll_vm vm4 10.0.0.49 2225 'C:/w3w' 'C:\w3w' "$VPY"
roll_vm vm5 10.0.0.49 2226 'C:/w3w' 'C:\w3w' "$VPY"

# laptop (different user/dir/py)
echo "--- laptop (10.0.0.49:22) ---"
LSDIR='C:/Users/Nehoray_Cohen/Projects/w3_laptop_worker'          # fwd-slash for scp
LDIR='C:\Users\Nehoray_Cohen\Projects\w3_laptop_worker'          # backslash for powershell
if scp -i "$KEY" -P 22 -o StrictHostKeyChecking=no -o ConnectTimeout=20 "Nehoray_Cohen@10.0.0.49:$LSDIR/corpus.json" "$TMP/laptop.json" 2>/dev/null; then
  genderize "$TMP/laptop.json"
  scp -i "$KEY" -P 22 -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$TMP/laptop.json" "Nehoray_Cohen@10.0.0.49:$LSDIR/corpus.json" 2>/dev/null
  scp -i "$KEY" -P 22 -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$NIM" "Nehoray_Cohen@10.0.0.49:$LSDIR/w3_nim.py" 2>/dev/null
  ssh -i "$KEY" -p 22 -o StrictHostKeyChecking=no -o ConnectTimeout=20 "Nehoray_Cohen@10.0.0.49" \
    "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | ?{\$_.CommandLine -match 'w3_nim'} | %{Stop-Process -Id \$_.ProcessId -Force}; Start-Sleep 2; (Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='$LPY -u $LDIR\\w3_nim.py'; CurrentDirectory='$LDIR'}).ProcessId\"" 2>/dev/null | tr -d '\r'
  echo "  laptop relaunched gender-aware"
else echo "  laptop scp pull FAILED — skip"; fi
echo "=== rollout done ==="
