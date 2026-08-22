#!/bin/bash
# AC2 fleet pull+bank: scp each stream's out.json -> banks/, merge into hebrew.json,
# canonicalise proper names, log progress. One-shot (locked); run from a Scheduled Task.
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/fleet"
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
# Windows-style path for the self-heal below (Invoke-CimMethod runs under
# powershell.exe and cannot execute an MSYS "/c/..." path). Same as pull_cpqa's $LPY.
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
LOG=/c/tmp/ac2_pull.log
LOCK=/c/tmp/ac2_pull.lock
if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 150 ] && exit 0
fi
touch "$LOCK"

# self-heal the live-progress pusher (gameId=ac2, sentences) — relaunch WINDOWLESS if it died.
# Same pattern as pull_cpqa.sh; without this a crash/reboot silently freezes the homepage tab.
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'ac2_progress'})) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u ac2_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null }" >/dev/null 2>&1

pull(){ # name host port user remotedir  — fetch each provider's out file (+ legacy out.json)
  for suf in _groq _sambanova _nim ""; do
    local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    timeout 40 scp -i "$KEY" -P "$3" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 "$4@$2:$5/out$suf.json" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}
pull vm3 127.0.0.1 2224 vboxuser "C:/ac2w"

# desktop stream is LOCAL - validate + copy each provider's out file (no scp)
for suf in _groq _sambanova _nim ""; do
  DW="$FLEET/desktop_worker/out$suf.json"
  if [ -s "$DW" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$DW" 2>/dev/null; then
    cp -f "$DW" "$BANKS/out_desktop$suf.json"
  fi
done

FLEETWIN="$(cygpath -w "$FLEET")"
"$PY" -X utf8 - <<PYEOF >> "$LOG" 2>&1
import json, os, glob, time, re
FLEET = r"$FLEETWIN"; BANKS = os.path.join(FLEET, "banks")
corpus = json.load(open(os.path.join(FLEET, "corpus_full.json"), encoding="utf-8"))

# --- canonical names: applied at MERGE, so a later correction needs no re-translation ----
fixes = []
try:
    reg = json.load(open(os.path.join(FLEET, "name_registry.json"), encoding="utf-8"))
    for grp in ("characters", "places", "factions_terms"):
        for en, he in (reg.get(grp) or {}).items():
            fixes.append((en, he))
    fixes.sort(key=lambda p: -len(p[0]))          # longest first: 'Ezio Auditore' before 'Ezio'
except Exception:
    pass
try:
    for a, b in json.load(open(os.path.join(FLEET, "name_fixes.json"), encoding="utf-8")):
        fixes.insert(0, (a, b))                   # explicit wrong->right pairs win
except Exception:
    pass

def canon(s):
    for a, b in fixes:
        if a and a in s: s = s.replace(a, b)
    return s

merged = {}
for f in sorted(glob.glob(os.path.join(BANKS, "out_*.json"))):
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    for k, v in d.items():
        if isinstance(v, str) and v.strip(): merged[k] = canon(v.strip())

heb_path = os.path.join(FLEET, "hebrew.json")
if os.path.exists(heb_path):
    try:
        old = json.load(open(heb_path, encoding="utf-8"))
        for k, v in old.items(): merged.setdefault(k, v)
    except Exception: pass
tmp = heb_path + ".tmp"
json.dump(merged, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, heb_path)

ui  = sum(1 for k in merged if k.startswith("ui:"))
sub = len(merged) - ui
tui = sum(1 for k in corpus if k.startswith("ui:"))
tsu = len(corpus) - tui
print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  total {len(merged)}/{len(corpus)} "
      f"({100.0*len(merged)/max(1,len(corpus)):.1f}%)  ui {ui}/{tui}  sub {sub}/{tsu}")
PYEOF
tail -1 "$LOG"
rm -f "$LOCK"
