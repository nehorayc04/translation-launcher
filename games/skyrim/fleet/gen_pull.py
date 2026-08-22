import os

script = r"""#!/bin/bash
# Skyrim fleet pull+bank. Pulls from all 7 machines.

set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/skyrim/fleet"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
LOG=/c/tmp/skyrim_pull.log
LOCK=/c/tmp/skyrim_pull.lock
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10"

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# keep the live-progress pusher alive
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'skyrim_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u skyrim_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

pull_ssh() { # $1 name  $2 user  $3 host  $4 port  $5 dir
  for suf in _groq _sambanova _nim; do
    local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    timeout 70 scp $SSHO -P "$4" "$2@$3:$5/out$suf.json" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}

pull_local() { # $1 name  $2 dir
  for suf in _groq _sambanova _nim; do
    local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    cp "$2/out$suf.json" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}

pull_local desktop "C:/skyrimw" &
pull_ssh laptop "Nehoray_Cohen" "10.0.0.49" 22 "C:/Users/Nehoray_Cohen/Projects/skyrim_worker" &
pull_ssh vm4 "vboxuser" "10.0.0.49" 2225 "C:/skyrimw" &
pull_ssh vm5 "vboxuser" "10.0.0.49" 2226 "C:/skyrimw" &
pull_ssh vm "vboxuser" "127.0.0.1" 2222 "C:/skyrimw" &
pull_ssh vm2 "vboxuser" "127.0.0.1" 2223 "C:/skyrimw" &
pull_ssh vm3 "vboxuser" "127.0.0.1" 2224 "C:/skyrimw" &
wait

FLEETWIN="$(cygpath -w "$FLEET")"
"$PY" -X utf8 - <<PYEOF >> "$LOG" 2>&1
import json, os, glob, time
FLEET = r"$FLEETWIN"; BANKS = os.path.join(FLEET, "banks")
corpus = json.load(open(os.path.join(FLEET, "corpus.json"), encoding="utf-8"))

merged = {}
for f in sorted(glob.glob(os.path.join(BANKS, "out_*.json"))):
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    for k, v in d.items():
        if isinstance(v, str) and v.strip(): merged[k] = v.strip()
heb = os.path.join(FLEET, "hebrew.json")
if os.path.exists(heb):
    try:
        for k, v in json.load(open(heb, encoding="utf-8")).items(): merged.setdefault(k, v)
    except Exception: pass
tmp = heb + ".tmp"
json.dump(merged, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, heb)
print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  total {len(merged)}/{len(corpus)} ({100.0*len(merged)/max(1,len(corpus)):.2f}%)")
PYEOF
tail -1 "$LOG"
rm -f "$LOCK"
"""

with open(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\skyrim\fleet\pull_skyrim.sh", "w", encoding="utf-8", newline='\n') as f:
    f.write(script)

with open(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\skyrim\fleet\pull_skyrim.bat", "w", encoding="utf-8") as f:
    f.write("@echo off\nbash pull_skyrim.sh\n")

print("Created pull scripts.")
