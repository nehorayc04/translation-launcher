#!/bin/bash
# CP2077 QA pull+merge+audit+heal. scp each stream's out.json -> banks/, merge into cpqa_out.json,
# emit cpqa_fixes.jsonl (every PROPOSED change with en/sec/iss/old/new for a human audit BEFORE any
# bake), heal a dead worker (relaunch windowless if its slice isn't done), log progress. One-shot
# (locked); run in a hidden background loop.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077/fleet"
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LOG=/c/tmp/cpqa_pull.log
LOCK=/c/tmp/cpqa_pull.lock
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=5"
VPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 150 ] && exit 0
fi
touch "$LOCK"
# temporarily-paused streams (one name per line in fleet/paused_streams) are NOT healed/relaunched,
# so a stream can be freed for other work without the 3-min heal fighting back. Their slice just
# waits; remove the name to resume. (Pull still scp's their out.json so no review is lost.)
PAUSED=" $(cat "$FLEET/paused_streams" 2>/dev/null | tr '\n' ' ') "
# keep the CP2077 dashboard pusher alive (relaunch windowless if it died)
# Start-if-absent AND kill-the-extras: two overlapping pull runs once raced this check and
# left TWO pushers, which both append to *_progress_hist.json — the duplicated samples make
# the rate window read 0/h on a perfectly healthy fleet, i.e. a false "stuck" on the homepage.
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'cpqa_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u cpqa_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

# 🔴 The laptop (and its vm4/vm5 guests) is normally reached over TAILSCALE, but Tailscale on THIS
# host can come up LOGGED OUT after a reboot — a boot-time DNS race: "fetch control key: failed to
# resolve controlplane.tailscale.com". Seen 2026-07-24: all 9 CP2077 workers were perfectly healthy
# and producing (every w_*.log fresh), yet every scp here timed out, so the MERGE stopped dead: the
# dashboard froze and reviewed work piled up un-banked on the remote disks. The same machines answer
# on the LAN, so resolve the host ONCE per run and fall back rather than lose the pull entirely.
# Tailscale stays preferred (it works off-LAN); LAN is the safety net.
LAPTOP_TS=100.116.78.88
LAPTOP_LAN=10.0.0.49
LAPTOP_H="$LAPTOP_TS"
if ! timeout 8 ssh $SSHO -p 22 "Nehoray_Cohen@$LAPTOP_TS" exit 2>/dev/null; then
  if timeout 8 ssh $SSHO -p 22 "Nehoray_Cohen@$LAPTOP_LAN" exit 2>/dev/null; then
    LAPTOP_H="$LAPTOP_LAN"
    echo "$(date '+%F %T')  NOTE tailscale unreachable -> falling back to LAN $LAPTOP_LAN" >> "$LOG"
  fi
fi

pull(){ # name host port user remoteOut(fwd) -- fetch each provider's out file (+ legacy out.json)
  local dir="${5%/out.json}"
  for suf in _groq _sambanova _nim ""; do
    local dest="$BANKS/out_$1$suf.json" tmp="$BANKS/out_$1$suf.json.tmp"; rm -f "$tmp"
    timeout 45 scp $SSHO -P "$3" "$4@$2:$dir/out$suf.json" "$tmp" 2>/dev/null
    if [ -s "$tmp" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$dest"
    else rm -f "$tmp"; fi
  done
}

heal(){ # name host port user py wdir(back)
  local n=$1 h=$2 p=$3 u=$4 py=$5 wb=$6
  case "$PAUSED" in *" $n "*) return 0 ;; esac   # paused stream -> do NOT relaunch
  local alive
  # 🔴 Count only PINNED (per-provider) workers, and require all THREE. The old check counted ANY
  # cpqa_nim and only fired at 0 — so the moment the 3 pinned workers finished their md5%3 thirds
  # and exited, it spawned ONE ARGUMENT-LESS worker instead: that legacy form reads the machine's
  # WHOLE corpus with no partition and writes out.json (no suffix), i.e. it re-reviews lines other
  # machines already own. Measured 2026-07-26: that is a live source of the 27% duplicate reviews,
  # and it was running on vm4 + vm5. Relaunch via the machine's SYSTEM task (run3.bat, 3 pinned
  # providers) — the only launcher proven to persist in session 0; the per-provider PID-lock makes
  # it idempotent, so firing it while some workers live is harmless.
  alive=$(ssh $SSHO -p "$p" "$u@$h" "powershell -NoProfile -Command \"(Get-CimInstance Win32_Process -Filter \\\"name='python.exe'\\\" | ?{\$_.CommandLine -match 'cpqa_nim.py (groq|sambanova|nim)'} | Measure-Object).Count\"" 2>/dev/null | tr -d '\r ')
  if [ -n "$alive" ] && [ "$alive" -lt 3 ] 2>/dev/null; then
    ssh $SSHO -p "$p" "$u@$h" "schtasks /run /tn CpqaMP" >/dev/null 2>&1
    echo "$(date '+%F %T')  HEAL $n: $alive/3 pinned -> ran CpqaMP" >> "$LOG"
  fi
}

pull vm     127.0.0.1 2222 vboxuser      "C:/cp2077qa/out.json"
pull vm2    127.0.0.1 2223 vboxuser      "C:/cp2077qa/out.json"
pull vm3    127.0.0.1 2224 vboxuser      "C:/cp2077qa/out.json"
pull vm4    $LAPTOP_H 2225 vboxuser      "C:/cp2077qa/out.json"
pull vm5    $LAPTOP_H 2226 vboxuser      "C:/cp2077qa/out.json"
pull laptop $LAPTOP_H 22   Nehoray_Cohen "C:/Users/Nehoray_Cohen/Projects/cp2077qa_worker/out.json"
# desktop = LOCAL worker dir (no scp)
DW="$FLEET/desktop_worker/out.json"
if [ -s "$DW" ] && "$PY" -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$DW" 2>/dev/null; then
  cp -f "$DW" "$BANKS/out_desktop.json"
fi

heal vm     127.0.0.1 2222 vboxuser      "$VPY" 'C:\cp2077qa'
heal vm2    127.0.0.1 2223 vboxuser      "$VPY" 'C:\cp2077qa'
heal vm3    127.0.0.1 2224 vboxuser      "$VPY" 'C:\cp2077qa'
heal vm4    $LAPTOP_H 2225 vboxuser      "$VPY" 'C:\cp2077qa'
heal vm5    $LAPTOP_H 2226 vboxuser      "$VPY" 'C:\cp2077qa'
heal laptop $LAPTOP_H 22   Nehoray_Cohen "$LPY" 'C:\Users\Nehoray_Cohen\Projects\cp2077qa_worker'
# desktop LOCAL heal: relaunch windowless via hidden.vbs if its own cpqa_nim isn't alive (cpqa.lock
# in desktop_worker/ makes a redundant relaunch self-exit, so this is idempotent)
dcount=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'desktop_worker' -and \$_.CommandLine -match 'cpqa_nim'} | Measure-Object).Count" 2>/dev/null | tr -d '\r ')
case "$PAUSED" in *" desktop "*) dcount=1 ;; esac   # paused -> skip desktop relaunch
if [ "${dcount:-0}" = "0" ] && [ -f "$FLEET/desktop_worker/run.bat" ]; then
  DRUN="$(cygpath -w "$FLEET/desktop_worker/run.bat")"; VBSW="$(cygpath -w "$FLEET/hidden.vbs")"
  powershell -NoProfile -Command "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='wscript.exe \"$VBSW\" \"$DRUN\"'} | Out-Null" 2>/dev/null
  echo "$(date '+%F %T')  HEAL relaunched desktop" >> "$LOG"
fi

# ── freeze auto-recovery (LOCAL VirtualBox VMs only) ──────────────────────────────────
# A guest that thrashes on host memory freezes so hard its sshd can't even send a banner -> the heal
# (which SSHs in) can't revive it. Root cause was fixed by right-sizing VM RAM (no host over-commit),
# but as a safety net: if a local VM's bank is STALE and its SSH banner TIMES OUT, hard-reset it
# (poweroff+start), rate-limited so a reboot isn't re-triggered mid-boot. vm4/vm5/laptop are remote
# (can't VBox-control from here) — their heal covers a mere dead worker; only a full guest freeze on
# THIS host needs this.
VBM="/c/Program Files/Oracle/VirtualBox/VBoxManage.exe"; [ -x "$VBM" ] || VBM="VBoxManage.exe"
freeze_recover(){ # vmname port bankname
  local vm="$1" port="$2" bank="$BANKS/out_$3.json" mark="/c/tmp/cpqa_reset_$3.ts"
  case "$PAUSED" in *" $3 "*) return 0 ;; esac
  [ -f "$bank" ] || return 0
  local age=$(( ($(date +%s) - $(stat -c %Y "$bank")) / 60 ))
  [ "$age" -lt 25 ] && return 0
  if [ -f "$mark" ]; then local since=$(( ($(date +%s) - $(stat -c %Y "$mark")) / 60 )); [ "$since" -lt 15 ] && return 0; fi
  timeout 18 ssh $SSHO -p "$port" vboxuser@127.0.0.1 "echo ok" >/dev/null 2>&1 && return 0  # SSH ok -> not frozen
  touch "$mark"
  "$VBM" controlvm "$vm" poweroff >/dev/null 2>&1; sleep 3
  "$VBM" startvm "$vm" --type headless >/dev/null 2>&1
  echo "$(date '+%F %T')  FREEZE-RECOVER hard-reset $vm (bank ${age}m stale + SSH banner-timeout)" >> "$LOG"
}
freeze_recover "Win11 - 1"   2222 vm
freeze_recover "Win11-VM-2"  2223 vm2
freeze_recover "Win11-VM-3"  2224 vm3

# merge + audit
FLEETWIN="$(cygpath -w "$FLEET")"
"$PY" -X utf8 - "$FLEETWIN" >> "$LOG" 2>&1 <<'PYEOF'
import json, os, glob, sys, time, shutil
FLEET = sys.argv[1]; BANKS = os.path.join(FLEET, "banks")
corpus = json.load(open(os.path.join(FLEET, "qa_corpus.json"), encoding="utf-8"))
OUTP = os.path.join(FLEET, "cpqa_out.json")
FIXP = os.path.join(FLEET, "cpqa_fixes.jsonl")
merged = {}
# MONOTONIC seed: never let a worker reset / re-deploy (a VM's out.json wiped) erase
# already-reviewed lines or the human audit trail — cpqa_out.json can only GROW. A key that
# gets re-reviewed just takes the newer worker answer; nothing already accumulated is dropped.
if os.path.exists(OUTP):
    try:
        for k, v in json.load(open(OUTP, encoding="utf-8")).items():
            if isinstance(v, dict) and isinstance(v.get("he"), str):
                merged[k] = v
    except Exception:
        pass
for f in glob.glob(os.path.join(BANKS, "out_*.json")):
    try:
        for k, v in json.load(open(f, encoding="utf-8")).items():
            if isinstance(v, dict) and isinstance(v.get("he"), str):
                merged[k] = v
    except Exception:
        pass
# one-deep recovery backups before overwrite
for p in (OUTP, FIXP):
    if os.path.exists(p):
        try: shutil.copy2(p, p + ".prev")
        except Exception: pass
json.dump(merged, open(OUTP, "w", encoding="utf-8"), ensure_ascii=False)
# SAFETY: the worker's he_gender() misses bare imperative forms (קרא/קראי, פרץ/פרצי, נעל/נעלי),
# so llama-70b's masculine-izing/feminine-izing of a genderless-English UI button slips its guard
# tagged "phrasing". Route any old->new that is ONLY a Hebrew addressee-gender morpheme flip, with
# NO Arabic ground truth (ag not in m/f/pl), to a SEPARATE suspect file — never into the bake queue.
import re as _re
_GW = _re.compile(r'(?<![א-ת])(אתה|אתן|אתם|את)(?![א-ת])')
_FIN = str.maketrans("ךםןףץ", "כמנפצ")     # normalize final forms (פרצי<->פרץ, ט has none)
def _gflip(old, new, ag):
    if ag in ("m", "f", "pl"):
        return False                      # game's Arabic decides -> a real, verified fix
    a, b = old.strip().translate(_FIN), new.strip().translate(_FIN)
    if not a or a == b:
        return False
    if a == b + "י" or b == a + "י":      # feminine-imperative י add/drop (Read/Hack/Lock class)
        return True
    if _GW.sub("▢", a) == _GW.sub("▢", b): # אתה<->את / אתם<->אתן swap, rest identical
        return True
    return False
# audit trail: every proposed change (he != original)
fixes = []; suspect = []
for k, v in merged.items():
    c = corpus.get(k)
    if not c:
        continue
    if v.get("iss", "ok") != "ok" and v["he"] != c["he"]:
        r = {"id": k, "sec": c.get("sec"), "iss": v["iss"],
             "en": c["en"], "old": c["he"], "new": v["he"], "ag": c.get("ag")}
        (suspect if _gflip(c["he"], v["he"], c.get("ag")) else fixes).append(r)
with open(os.path.join(FLEET, "cpqa_fixes.jsonl"), "w", encoding="utf-8") as fo:
    for r in fixes:
        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(os.path.join(FLEET, "cpqa_fixes_suspect.jsonl"), "w", encoding="utf-8") as fo:
    for r in suspect:
        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
by = {}
for r in fixes:
    by[r["iss"]] = by.get(r["iss"], 0) + 1
tot = len(corpus)
print(f"{time.strftime('%F %T')}  CPQA reviewed {len(merged)}/{tot} ({100*len(merged)/tot:.1f}%)  "
      f"fixes {len(fixes)}  suspect {len(suspect)}  {by}")
PYEOF
tail -1 "$LOG"
rm -f "$LOCK"
