#!/usr/bin/env bash
# Pull the vm5 "New Era" TRANSLATE+multi-lang-gender worker (w3ut), fold its out.json into
# fleet/hebrew.json, and record every folded id into w3_newera_passed.json so the later multi-lang
# REVIEW pass (w3qa) SKIPS them — they were already gender/context-verified at translation time.
cd "$(dirname "$0")" || exit 1
mkdir -p w3ut_banks
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
# keep the New-Era live-progress pusher alive (relaunch windowless if it died)
VBS='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\hidden.vbs'
PBAT='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet\run_w3ut_progress.bat'
PDIR='C:\Users\Nehoray_Cohen\Projects\Game translator\games\witcher3\fleet'
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'w3ut_progress'})) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wscript.exe \"$VBS\" \"$PBAT\"'; CurrentDirectory='$PDIR'} | Out-Null }" >/dev/null 2>&1
# --- pull each stream's out.json (laptop host; LAN first, then Tailscale). ---
pull() { # name host port
  scp -i ~/.ssh/id_ed25519 -P "$3" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 \
      "vboxuser@$2:C:/w3ut/out.json" "w3ut_banks/out_$1.json.tmp" >/dev/null 2>&1 \
    && "$PY" -c "import json;json.load(open('w3ut_banks/out_$1.json.tmp'))" 2>/dev/null \
    && mv -f "w3ut_banks/out_$1.json.tmp" "w3ut_banks/out_$1.json" && return 0
  rm -f "w3ut_banks/out_$1.json.tmp"; return 1
}
pull vm5 10.0.0.49 2226 || pull vm5 100.116.78.88 2226 || echo "  vm5 pull FAILED (keeping last bank)"
pull vm4 10.0.0.49 2225 || pull vm4 100.116.78.88 2225 || echo "  vm4 pull FAILED (keeping last bank)"
# --- fold every bank into hebrew.json (ADD only — these are freshly-translated ids) + mark New-Era-passed ---
"$PY" - <<'PY'
import json, glob, os, re
HEB=re.compile(r'[֐-׿]'); AR=re.compile(r'[؀-ۿ]')
he=json.load(open("hebrew.json",encoding="utf-8"))
passed=set(json.load(open("w3_newera_passed.json",encoding="utf-8"))) if os.path.exists("w3_newera_passed.json") else set()
corp=json.load(open("w3ut_corpus.json",encoding="utf-8"))
added=0; bank={}
for f in glob.glob("w3ut_banks/out_*.json"):
    try: bank.update(json.load(open(f,encoding="utf-8")))
    except Exception: pass
for k,v in bank.items():
    if not isinstance(v,str) or not v.strip(): continue
    if not HEB.search(v) or AR.search(v): continue      # must be real Hebrew, no Arabic leak
    if he.get(k)!=v: added+=1
    he[k]=v
    passed.add(k)                                       # translated WITH multi-lang gender -> New-Era-verified
json.dump(he, open("hebrew.json.tmp","w",encoding="utf-8"), ensure_ascii=False); os.replace("hebrew.json.tmp","hebrew.json")
json.dump(sorted(passed), open("w3_newera_passed.json.tmp","w",encoding="utf-8"), ensure_ascii=False); os.replace("w3_newera_passed.json.tmp","w3_newera_passed.json")
done=sum(1 for k in corp if k in bank)
print(f"w3ut folded: banked {len(bank)} | corpus {len(corp)} | remaining {len(corp)-done} | +{added} into hebrew.json | New-Era-passed total {len(passed)}")
PY
