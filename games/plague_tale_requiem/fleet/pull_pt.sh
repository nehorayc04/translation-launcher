#!/bin/bash
# PT Requiem fleet pull+bank: scp each stream's out.json -> banks/, merge into hebrew.json, log progress.
# Mirrors the W3 pull. One-shot (locked); registered as a Windows Scheduled Task (every 3 min).
# Remote worker dir on each VM = C:\ptw ; laptop host = a separate project dir.
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/plague_tale_requiem/fleet"
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LOG=/c/tmp/pt_pull.log
LOCK=/c/tmp/pt_pull.lock
if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 150 ] && exit 0
fi
touch "$LOCK"
pull(){ # name host port user remotepath
  local dest="$BANKS/out_$1.json"; local tmp="$dest.tmp"; rm -f "$tmp"
  timeout 40 scp -i "$KEY" -P "$3" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$4@$2:$5" "$tmp" 2>/dev/null
  if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$dest"
  else rm -f "$tmp"; fi
}
pull vm     127.0.0.1 2222 vboxuser "C:/ptw/out.json"
pull vm2    127.0.0.1 2223 vboxuser "C:/ptw/out.json"
pull vm3    127.0.0.1 2224 vboxuser "C:/ptw/out.json"
pull vm4    100.116.78.88 2225 vboxuser "C:/ptw/out.json"
pull vm5    100.116.78.88 2226 vboxuser "C:/ptw/out.json"
pull laptop 100.116.78.88 22   Nehoray_Cohen "C:/Users/Nehoray_Cohen/Projects/pt_laptop_worker/out.json"
# desktop 7th stream is LOCAL — validate+copy (no scp)
DW="$FLEET/desktop_worker/out.json"
if [ -s "$DW" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding=\"utf-8\"))" "$DW" 2>/dev/null; then cp -f "$DW" "$BANKS/out_desktop.json"; fi
# merge all banks -> hebrew.json + progress (Windows path for the native python)
FLEETWIN="$(cygpath -w "$FLEET")"
"$PY" -X utf8 - <<PYEOF >> "$LOG" 2>&1
import json,os,glob,time
FLEET=r"$FLEETWIN"; BANKS=os.path.join(FLEET,"banks")
try: markers=set(json.load(open(os.path.join(FLEET,"marker_keys.json"),encoding="utf-8")))
except Exception: markers=set()
try: name_fixes=json.load(open(os.path.join(FLEET,"name_fixes.json"),encoding="utf-8"))
except Exception: name_fixes=[]
def canon(v):                                               # enforce consistent name spelling everywhere
    for w,r in name_fixes: v=v.replace(w,r)
    return v
merged={}
for f in glob.glob(os.path.join(BANKS,"out_*.json")):
    try:
        for k,v in json.load(open(f,encoding="utf-8")).items():
            if k in markers: continue                       # non-translatable marker -> keep Arabic
            if isinstance(v,str) and v.strip(): merged[k]=canon(v)
    except Exception: pass
# durable gender overlay: re-apply gender-review corrections on top of the bank rebuild so a
# concurrent PT pull can never wipe them (the gender review runs in fleet/gender/).
try:
    ov=json.load(open(os.path.join(FLEET,"gender_overrides.json"),encoding="utf-8"))
    for k,v in ov.items():
        if k in merged and isinstance(v,str) and v.strip(): merged[k]=v
except Exception: pass
tmp=os.path.join(FLEET,"hebrew.json.tmp")
json.dump(merged,open(tmp,"w",encoding="utf-8"),ensure_ascii=False); os.replace(tmp,os.path.join(FLEET,"hebrew.json"))
TOTAL=20661-len(markers)
print(f"{time.strftime('%F %H:%M:%S')}  PT banked {len(merged)}/{TOTAL} ({100*len(merged)/max(1,TOTAL):.1f}%)  [markers excluded {len(markers)}]")
PYEOF
rm -f "$LOCK"
