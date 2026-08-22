#!/bin/bash
# Pull the SM2 New-Era line-by-line QA review results from vm/vm2/vm3 into the banks.
# Review-only (ביקורת-בלבד): the banks keep {id:{he,iss}} before/after for a human audit BEFORE
# any bake. Nothing is baked or published here. One-shot (locked); run from a Scheduled Task.
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/spiderman2/fleet"
U=vboxuser
H=127.0.0.1
PY="C:\\Users\\Nehoray_Cohen\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
BANKS="$FLEET/banks"; mkdir -p "$BANKS"
LOCK=/c/tmp/sm2qa_pull.lock
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20"

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# self-heal the live-progress pusher (gameId=spiderman2, sentences) — relaunch WINDOWLESS if it died.
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'sm2qa_progress'})) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$PY\" -u sm2qa_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null }" >/dev/null 2>&1

# pull each stream's out_<prov>.json -> banks/out_<machine>_<prov>.json (validate before replacing:
# a hard power-cycle can leave a NUL-filled out.json, and a straight copy would destroy reviewed work).
for spec in "2222 vm" "2223 vm2" "2224 vm3"; do
  set -- $spec; P=$1; M=$2
  for suf in _groq _sambanova _nim; do
    tmp="$BANKS/.out_${M}${suf}.tmp"; dst="$BANKS/out_${M}${suf}.json"
    if scp $SSHO -P "$P" "$U@$H:C:/sm2qa/out$suf.json" "$tmp" 2>/dev/null; then
      if python -c "import json,sys; json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
        mv -f "$tmp" "$dst"
      else echo "  !! $M$suf out CORRUPT — bank kept"; rm -f "$tmp"; fi
    else rm -f "$tmp"; fi
  done
  echo "  pulled $M (groq/sambanova/nim)"
done

# worker heal: a machine with <3 pinned workers gets its SYSTEM task run (run3.bat, persists in
# session 0). The per-provider PID-lock makes a redundant relaunch self-exit, so this is harmless.
PINNED='sm2qa_nim.py (groq|sambanova|nim)'
for spec in "2222 vm" "2223 vm2" "2224 vm3"; do
  set -- $spec; P=$1; M=$2
  n=$(ssh $SSHO -p "$P" "$U@$H" "powershell -NoProfile -Command \"(Get-CimInstance Win32_Process -Filter \\\"name='python.exe'\\\" | ?{\$_.CommandLine -match '$PINNED'} | Measure-Object).Count\"" 2>/dev/null | tr -d '\r ')
  if [ -n "$n" ] && [ "$n" -lt 3 ] 2>/dev/null; then
    ssh $SSHO -p "$P" "$U@$H" "schtasks /run /tn SM2qaMP" >/dev/null 2>&1
    echo "  HEAL $M: $n/3 pinned -> ran SM2qaMP"
  fi
done

rm -f "$LOCK"
