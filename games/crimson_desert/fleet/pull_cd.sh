#!/bin/bash
# Crimson Desert דור-3 TRANSLATE pull+bank.
# Pulls the machines this game owns (games/crimson_desert/fleet/machines.json).
# Desktop joined as a 7th machine once Skyrim's automated fleet was retired (2026-08-10) --
# it is now pulled locally, same as pull_skyrim.sh's own pattern.

set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/crimson_desert/fleet"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
LOG=/c/tmp/cd_pull.log
LOCK=/c/tmp/cd_pull.lock
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10"

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# keep the live-progress pusher alive
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'cd_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u cd_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

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

pull_local desktop "C:/cdw" &
pull_ssh laptop "Nehoray_Cohen" "10.0.0.49" 22 "C:/Users/Nehoray_Cohen/Projects/cd_worker" &
pull_ssh vm4 "vboxuser" "10.0.0.49" 2225 "C:/cdw" &
pull_ssh vm5 "vboxuser" "10.0.0.49" 2226 "C:/cdw" &
pull_ssh vm "vboxuser" "127.0.0.1" 2222 "C:/cdw" &
pull_ssh vm2 "vboxuser" "127.0.0.1" 2223 "C:/cdw" &
pull_ssh vm3 "vboxuser" "127.0.0.1" 2224 "C:/cdw" &
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

# ---- THE BRAIN, RE-APPLIED AT MERGE -------------------------------------------------------
# 🔑 A term correction must fix the WHOLE corpus retroactively, without re-translating a
# single line: every wrong Hebrew `variant` a glossary entry lists is rewritten to the
# canonical form here, on every merge. So adding one pair to brain_glossary.json is enough --
# the fleet does not have to see the line again. Prefix-aware (one attached ו/ה/ב/ל/מ/כ/ש),
# never inside a Latin run. [[deterministic-localization-brain]]
_canon, _n_canon = [], 0
try:
    _g = json.load(open(os.path.join(FLEET, "brain_glossary.json"), encoding="utf-8"))
    import re as _re
    for _t in (_g.get("terms") or []):
        for _bad in (_t.get("variants") or []):
            if _bad and _t.get("he") and _bad != _t["he"]:
                _canon.append((_re.compile(r"(?<![א-ת])((?:[והבלמכש])?)"
                                           + _re.escape(_bad) + r"(?![א-ת])"),
                               lambda m, he=_t["he"]: m.group(1) + he))
except Exception as _e:
    print("[brain] canon skipped:", _e)
if _canon:
    for _k, _v in merged.items():
        _s0 = _v.get("he", "")
        _s = _s0
        for _rx, _rep in _canon: _s = _rx.sub(_rep, _s)
        if _s != _s0:
            _v["he"] = _s; _n_canon += 1
    # report the EFFECT, never just "it ran" -- a transform that silently changes 0 rows is
    # indistinguishable from a broken one. [[verify-a-transform-by-counting-its-effect]]
    print(f"  brain canon: {len(_canon)} pairs applied to {_n_canon} lines")

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
