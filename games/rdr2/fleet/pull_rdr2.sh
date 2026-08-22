#!/bin/bash
# RDR2 fleet pull+bank: scp each stream's out_<provider>.json -> banks/, merge into hebrew.json,
# heal a machine whose workers died, keep the dashboard pusher alive. One-shot (locked); run from
# a Scheduled Task every 3 min.
#
# Two rules this script exists to enforce, both learned the hard way (CLAUDE.md classes #6/#7):
#   * NEVER overwrite a bank with something that is not valid JSON — a hard-killed worker leaves a
#     NUL-filled out.json, and a straight scp would propagate that over good reviewed work.
#   * heal by running the machine's SYSTEM task, never by launching a worker over ssh (an
#     ssh-launched process dies with the session; only run3.bat under the task persists).
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/rdr2/fleet"
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
LOG=/c/tmp/rdr2_pull.log
LOCK=/c/tmp/rdr2_pull.lock
# Laptop reach: use the LAN IP while it is on the same network as this desktop; the Tailscale IP
# (100.116.78.88) is unreachable from here because the desktop's Avast SecureLine VPN EACCES-blocks
# outbound TCP to the 100.x CGNAT range, while the laptop must KEEP its own VPN. When the laptop
# leaves the LAN, flip this back to 100.116.78.88 (and clear the desktop VPN block).
H=10.0.0.49
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10 -o ServerAliveCountMax=3"

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# keep the live-progress pusher alive (start if absent, kill any extra — two pushers append to the
# same history file and make the rate window read 0/h on a perfectly healthy fleet).
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'rdr2_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u rdr2_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

pull(){ # $1 label  $2 port  $3 user  $4 remotedir  -- reaches $H (the laptop, LAN/Tailscale)
  for suf in _groq _sambanova _nim; do
    local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    timeout 70 scp $SSHO -P "$2" "$3@$H:$4/out$suf.json" "$tmp" 2>/dev/null
    # validate BEFORE replacing the bank — a NUL/truncated file must never reach it
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
  # NO heal ssh here. A synchronous `schtasks /run` inside the pull blocks for the whole ssh
  # timeout on a slow/off-LAN machine, so the pulls PILE UP holding the lock and the banks stop
  # updating while the workers keep translating. The pull's only job is to scp banks; reviving a
  # dead worker belongs to the machine's own RdrMP (5-min) + RdrMPBoot (on-start) tasks.
}
pull_localvm(){ # $1 label  $2 port  $3 user  $4 remotedir  -- local VirtualBox VM on 127.0.0.1
  # vm/vm2/vm3 (Win11-VM 1/2/3) — added 2026-08-03 when spiderman2 finished and its 9 streams
  # were repointed at rdr2. Same as pull() but against 127.0.0.1, not the laptop's $H.
  for suf in _groq _sambanova _nim; do
    local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    timeout 70 scp $SSHO -P "$2" "$3@127.0.0.1:$4/out$suf.json" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}
pull_local(){ # $1 label  $2 localdir(msys path) — the desktop is LOCAL (no scp), just validate+copy.
  for suf in _groq _sambanova _nim; do
    local src="$2/out$suf.json"; local dest="$BANKS/out_$1$suf.json"; local tmp="$dest.tmp"; rm -f "$tmp"
    [ -f "$src" ] || continue
    cp -f "$src" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}
pull laptop 22   Nehoray_Cohen "C:/Users/Nehoray_Cohen/Projects/rdr2_worker" &
pull vm4    2225 vboxuser      "C:/rdr2w" &
pull vm5    2226 vboxuser      "C:/rdr2w" &
pull_local desktop "/c/rdr2wd" &
wait
# vm/vm2/vm3 (pull_localvm, defined above) are DELIBERATELY left idle/free — see the 2026-08-03
# note: they were briefly folded into rdr2 (streams #27-35) and put back on the user's request.

FLEETWIN="$(cygpath -w "$FLEET")"
"$PY" -X utf8 - <<PYEOF >> "$LOG" 2>&1
import json, os, glob, time
FLEET = r"$FLEETWIN"; BANKS = os.path.join(FLEET, "banks")
corpus = json.load(open(os.path.join(FLEET, "corpus.json"), encoding="utf-8"))
# --- canonical names applied at MERGE, so a later correction costs no re-translation --------
fixes = []
try:
    reg = json.load(open(os.path.join(FLEET, "name_registry.json"), encoding="utf-8"))
    for grp in ("characters", "places", "factions", "systems", "gear"):
        for en, he in (reg.get(grp) or {}).items():
            if en and he: fixes.append((en, he))
    fixes.sort(key=lambda p: -len(p[0]))     # longest first: 'Gold Bars' before 'Gold Bar'
except Exception: pass
try:
    nf = json.load(open(os.path.join(FLEET, "name_fixes.json"), encoding="utf-8"))
    for a, b in (nf.get("pairs") or []):
        fixes.insert(0, (a, b))              # explicit wrong->right Hebrew wins
except Exception: pass

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
