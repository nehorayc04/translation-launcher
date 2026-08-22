#!/bin/bash
# Spider-Man 2 New-Era-2 review pull+bank.
# Pulls ONLY the six machines this game owns (games/spiderman2/fleet/machines.json).
# The desktop is finishing Skyrim, so touching it here would bank another game's output.

set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/spiderman2/fleet"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
LOG=/c/tmp/sm2_pull.log
LOCK=/c/tmp/sm2_pull.lock
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10"

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# keep the live-progress pusher alive
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'sm2qa_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u sm2qa_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

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

pull_ssh laptop "Nehoray_Cohen" "10.0.0.49" 22 "C:/Users/Nehoray_Cohen/Projects/sm2_worker" &
pull_ssh vm4 "vboxuser" "10.0.0.49" 2225 "C:/sm2w" &
pull_ssh vm5 "vboxuser" "10.0.0.49" 2226 "C:/sm2w" &
pull_ssh vm "vboxuser" "127.0.0.1" 2222 "C:/sm2w" &
pull_ssh vm2 "vboxuser" "127.0.0.1" 2223 "C:/sm2w" &
pull_ssh vm3 "vboxuser" "127.0.0.1" 2224 "C:/sm2w" &
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
        # ⚠️ a REVIEW bank is {id:{he,iss}}, NOT {id:"hebrew"} -- a str-only merge
        # silently drops every row and reports 0%. [[fleet-qa-review-hardening]]
        if isinstance(v, dict) and str(v.get("he", "")).strip(): merged[k] = v
        elif isinstance(v, str) and v.strip(): merged[k] = {"he": v.strip(), "iss": "ok"}
heb = os.path.join(FLEET, "hebrew.json")
if os.path.exists(heb):
    try:
        for k, v in json.load(open(heb, encoding="utf-8")).items(): merged.setdefault(k, v)
    except Exception: pass
tmp = heb + ".tmp"
json.dump(merged, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, heb)
print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  total {len(merged)}/{len(corpus)} ({100.0*len(merged)/max(1,len(corpus)):.2f}%)")

# ---- AUTO-RESLICE ------------------------------------------------------------------------
# A worker EXITS when its own shard drains ("slice drained - done."), which the dashboard
# correctly shows as מת. With a fixed shard that means the fleet winds itself down stream by
# stream while thousands of lines still wait in OTHER shards -- the user sees a table full of
# dead streams and has to ask for a manual reslice every time. So: decide it here, on the one
# job that already knows the true global remainder.
#   * only when the work left genuinely needs the fleet (>= MIN_LEFT),
#   * only when a stream has actually drained (or a shard file is missing),
#   * and at most once every COOLDOWN_S, so a slow pass can never thrash the fleet.
MIN_LEFT, COOLDOWN_S = 400, 900
stamp = os.path.join(FLEET, ".last_reslice")
left = len(corpus) - len(merged)
try:
    over = set(json.load(open(os.path.join(FLEET, "oversized.json"), encoding="utf-8")))
except Exception:
    over = set()
left -= len(over & (corpus.keys() - merged.keys()))
drained = []
nshards = 0
for f in sorted(glob.glob(os.path.join(FLEET, "shards", "corpus_*.json"))):
    try: sh = set(json.load(open(f, encoding="utf-8")).keys())
    except Exception: continue
    nshards += 1
    if not (sh - merged.keys()):
        drained.append(os.path.basename(f))
age = time.time() - (os.path.getmtime(stamp) if os.path.exists(stamp) else 0)
if left >= MIN_LEFT and drained and age >= COOLDOWN_S:
    print(f"  auto-reslice: {left} lines left, {len(drained)} of {nshards} shards drained")
    open(stamp, "w").write(str(time.time()))
    import subprocess, sys
    for script in ("reslice_equal.py", "push_shards_restart.py"):
        r = subprocess.run([sys.executable, os.path.join(FLEET, script)],
                           capture_output=True, text=True, cwd=FLEET, timeout=600)
        for ln in (r.stdout or "").strip().splitlines():
            print("   " + ln)
        if r.returncode != 0:
            print(f"   {script} rc={r.returncode} {(r.stderr or '')[:200]}")
            break
elif drained:
    print(f"  {len(drained)}/{nshards} shards drained, {left} left "
          f"(reslice in {max(0, int(COOLDOWN_S - age))}s)" if left >= MIN_LEFT
          else f"  {len(drained)}/{nshards} shards drained, {left} left - tail, no reslice")
PYEOF
tail -3 "$LOG"
rm -f "$LOCK"
