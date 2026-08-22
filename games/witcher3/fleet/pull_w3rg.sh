#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
mkdir -p w3rg_banks
# keep the W3 dashboard pusher alive (relaunch windowless if it died)
PPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
PDIR='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet'
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'w3rg_progress'})) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$PPY\" -u w3rg_progress.py'; CurrentDirectory='$PDIR'} | Out-Null }" >/dev/null 2>&1
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
pull() { scp -i ~/.ssh/id_ed25519 -P "$3" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 "vboxuser@$2:$4" "w3rg_banks/out_$1.json.tmp" >/dev/null 2>&1 && "$PY" -c "import json;json.load(open('w3rg_banks/out_$1.json.tmp'))" 2>/dev/null && mv -f "w3rg_banks/out_$1.json.tmp" "w3rg_banks/out_$1.json" || rm -f "w3rg_banks/out_$1.json.tmp"; }
pull vm5 10.0.0.49 2226 "C:/w3rgw/out.json"
cp -f desktop_w3rg/out.json w3rg_banks/out_desktop.json 2>/dev/null
# fold the agent's reglue-tail output ({id: hebrew}) in as another bank (same format as a worker's out.json)
cp -f agent_reglue/hebrew.json w3rg_banks/out_agent.json 2>/dev/null
"$PY" - <<'PY'
import json, glob, os
he = {}
for f in glob.glob("w3rg_banks/out_*.json"):
    try: he.update(json.load(open(f, encoding="utf-8")))
    except Exception: pass
json.dump(he, open("reglue_hebrew.json.tmp","w",encoding="utf-8"), ensure_ascii=False)
os.replace("reglue_hebrew.json.tmp","reglue_hebrew.json")
tot=len(json.load(open("reglue_corpus.json",encoding="utf-8")))
print(f"reglue merged: {len(he)}/{tot}  remaining {tot-len(he)}")
PY
