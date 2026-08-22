#!/bin/bash
# Pull the New-Era QA review results from VM1 + VM2 and fold them into an AUDIT file.
#
# ⚠️ This does NOT touch fleet/hebrew.json — the reviewed lines are destined for the SECOND
# mod update, not for the build that is published now. The audit file keeps before/after so a
# human can approve before any bake (`apply_qa_review.py`).
set -u
KEY=~/.ssh/id_ed25519
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/witcher3/fleet"
U=vboxuser
H=127.0.0.1
PY="C:\\Users\\Nehoray_Cohen\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"
mkdir -p "$FLEET/banks"

# self-heal the live-progress pusher (gameId=witcher3, sentences) — relaunch WINDOWLESS if it died.
# Same pattern as pull_cpqa.sh; without this a crash/reboot silently freezes the homepage tab.
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'w3qa_progress'})) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$PY\" -u w3qa_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null }" >/dev/null 2>&1

for spec in "2222 0" "2223 1" "2224 2"; do
  set -- $spec; P=$1; N=$2
  # multi-provider: fetch each provider's out file (+ legacy out.json) as qa_out_<N><suf>.json
  for suf in _groq _sambanova _nim ""; do
    # 🔴 Land in a TEMP file and only replace the bank if it PARSES. A hard power-cycle
    # (the VM watchdog's hang recovery) can leave the guest's out_*.json allocated at full
    # size but filled with NULs — NTFS updated the metadata, never flushed the data. Copying
    # that straight over the bank destroyed ~2.5k reviewed lines on 2026-07-22, and the pull
    # reported success. A bank is only ever replaced by valid JSON.
    tmp="$FLEET/banks/.qa_out_${N}${suf}.tmp"
    dst="$FLEET/banks/qa_out_${N}${suf}.json"
    if scp -i "$KEY" -P "$P" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20 \
        "$U@$H:C:/w3qa/out$suf.json" "$tmp" 2>/dev/null; then
      if python -c "import json,sys; json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
        mv -f "$tmp" "$dst"
      else
        echo "  !! vm$((N+1))$suf out file is CORRUPT — bank kept, not overwritten"
        rm -f "$tmp"
      fi
    else
      rm -f "$tmp"
    fi
  done
  echo "  pulled vm$((N+1)) slice $N (groq/sambanova/nim)"
done

# desktop-local (slice 3): the freed AC2-desktop machine now reviews slice 3.
# Its worker writes C:\w3qad\out_*.json on THIS machine, so cp (no scp) into the banks.
for suf in _groq _sambanova _nim ""; do
  src="/c/w3qad/out$suf.json"; tmp="$FLEET/banks/.qa_out_3$suf.tmp"; dst="$FLEET/banks/qa_out_3$suf.json"
  [ -f "$src" ] || continue
  if cp -f "$src" "$tmp" 2>/dev/null && python -c "import json,sys; json.load(open(sys.argv[1],encoding='utf-8'))" "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$dst"
  else
    echo "  !! desktop$suf out CORRUPT — bank kept, not overwritten"; rm -f "$tmp"
  fi
done
echo "  pulled desktop slice 3 (local)"

# --- worker heal (added 2026-07-26). This pull had NO worker heal at all: it only revived the
# progress pusher, so a dead provider-stream stayed dead and its share of the corpus simply waited
# (that is how vm's sambanova sat idle). Judge a machine by how many PINNED workers it has, and
# relaunch through the launcher that is PROVEN to persist: the guest's own SYSTEM task (run3.bat,
# 3 pinned providers) on a VM, and a local detached run3.bat on this desktop (a worker started over
# ssh dies with the session; a LOCAL Start-Process persists). The per-provider PID-lock makes a
# redundant relaunch self-exit, so firing this while workers live is harmless.
PINNED='w3qa_nim.py (groq|sambanova|nim)'
for spec in "2222 vm" "2223 vm2" "2224 vm3"; do
  set -- $spec; P=$1; NM=$2
  n=$(ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 "$U@$H" \
      "powershell -NoProfile -Command \"(Get-CimInstance Win32_Process -Filter \\\"name='python.exe'\\\" | ?{\$_.CommandLine -match '$PINNED'} | Measure-Object).Count\"" 2>/dev/null | tr -d '\r ')
  if [ -n "$n" ] && [ "$n" -lt 3 ] 2>/dev/null; then
    ssh -i "$KEY" -p "$P" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 "$U@$H" \
      "schtasks /run /tn W3qaMP" >/dev/null 2>&1
    echo "  HEAL $NM: $n/3 pinned -> ran W3qaMP"
  fi
done
dn=$(MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'w3qa_nim.py (groq|sambanova|nim)'} | Measure-Object).Count" 2>/dev/null | tr -d '\r ')
if [ -n "$dn" ] && [ "$dn" -lt 3 ] 2>/dev/null; then
  MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c','C:\\w3qad\\run3.bat'" >/dev/null 2>&1
  echo "  HEAL desktop: $dn/3 pinned -> ran C:\\w3qad\\run3.bat"
fi

"/c/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe" "$FLEET/fold_qa_review.py"
