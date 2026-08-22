#!/bin/bash
# Corsair Cove fleet pull+bank: scp each stream's out_<provider>.json -> banks/, merge into
# hebrew.json, keep the dashboard pusher alive. One-shot (locked); run from a Scheduled Task.
#
# Streams 13-21 = vm / vm2 / vm3, the LOCAL VirtualBox guests on 127.0.0.1:2222-4 (NOT the
# laptop — RDR2 owns the laptop + vm4 + vm5 as streams 1-12).
#
# Two rules this script exists to enforce, both learned the hard way:
#   * NEVER overwrite a bank with something that is not valid JSON — a hard-killed worker
#     leaves a NUL-filled out.json, and a straight scp would propagate that over good work.
#   * do ONE fast thing. No blocking remote heal here: a synchronous `schtasks /run` over ssh
#     stalls the whole tick on a slow guest, the ticks pile up holding the lock, and the banks
#     silently stop updating while the workers keep translating. Reviving a dead worker is the
#     job of each machine's own CcMP (5 min) / CcMPBoot (on start) SYSTEM tasks.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/corsair_cove/fleet"
U=vboxuser
H=127.0.0.1
RD="C:/ccw"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
LOG=/c/tmp/cc_pull.log
LOCK=/c/tmp/cc_pull.lock
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10"

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# keep the live-progress pusher alive: start if absent, and KILL ANY EXTRA — two pushers append
# to the same history file and make the rate window read 0/h on a perfectly healthy fleet.
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'cc_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u cc_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

pull() { # $1 label  $2 port
  for suf in _groq _sambanova _nim; do
    local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    timeout 70 scp $SSHO -P "$2" "$U@$H:$RD/out$suf.json" "$tmp" 2>/dev/null
    # validate BEFORE replacing the bank — a NUL/truncated file must never reach it
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}
pull vm  2222 &
pull vm2 2223 &
pull vm3 2224 &
wait

FLEETWIN="$(cygpath -w "$FLEET")"
"$PY" -X utf8 - <<PYEOF >> "$LOG" 2>&1
import json, os, glob, re, time
FLEET = r"$FLEETWIN"; BANKS = os.path.join(FLEET, "banks")
corpus = json.load(open(os.path.join(FLEET, "corpus.json"), encoding="utf-8"))

# --- canonical names applied at MERGE, so a later correction costs no re-translation --------
# The registry was decided from the game's OWN locales and every term was validated to EXIST in
# the corpus. Here it only repairs the case where the model left the ENGLISH term standing in
# an otherwise-Hebrew line.
TOKEN = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}")
fixes = []
try:
    reg = json.load(open(os.path.join(FLEET, "name_registry.json"), encoding="utf-8"))
    for term, t in (reg.get("terms") or {}).items():
        if term and isinstance(t, dict) and t.get("he") and t.get("mode") != "keep":
            fixes.append((term, t["he"]))
    fixes.sort(key=lambda p: -len(p[0]))   # longest first: 'Fort Vandekroon' before 'Vandekroon'
except Exception as e:
    print("  [canon] registry unavailable:", e)

def canon(s):
    """Replace a leftover English term with its canonical Hebrew, but NEVER inside an engine
    token: an img tag whose id happens to be a registry word would be broken by a blind
    replace, so the string is split on tokens and only the prose parts are edited.

    NOTE this block lives in an UNQUOTED bash heredoc, so it must contain no backticks and
    no dollar-parens -- bash would evaluate them as command substitution."""
    if not fixes or not s:
        return s
    out, last = [], 0
    for m in TOKEN.finditer(s):
        out.append((s[last:m.start()], True)); out.append((m.group(0), False)); last = m.end()
    out.append((s[last:], True))
    res = []
    for part, editable in out:
        if editable:
            for a, b in fixes:
                if a in part:
                    part = re.sub(r"(?<![A-Za-z])" + re.escape(a) + r"(?![A-Za-z])", b, part)
        res.append(part)
    return "".join(res)

merged = {}
for f in sorted(glob.glob(os.path.join(BANKS, "out_*.json"))):
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    for k, v in d.items():
        if isinstance(v, str) and v.strip(): merged[k] = canon(v.strip())
heb = os.path.join(FLEET, "hebrew.json")
if os.path.exists(heb):                      # monotonic: never lose an already-banked line
    try:
        for k, v in json.load(open(heb, encoding="utf-8")).items(): merged.setdefault(k, canon(v))
    except Exception: pass
tmp = heb + ".tmp"
json.dump(merged, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, heb)
cats = {}
for k in merged:
    c = (corpus.get(k) or {}).get("sec", "?")
    cats[c] = cats.get(c, 0) + 1
print(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  total {len(merged)}/{len(corpus)} "
      f"({100.0*len(merged)/max(1,len(corpus)):.2f}%)  " +
      "  ".join(f"{c}={n}" for c, n in sorted(cats.items(), key=lambda x: -x[1])))
PYEOF
tail -1 "$LOG"
rm -f "$LOCK"
