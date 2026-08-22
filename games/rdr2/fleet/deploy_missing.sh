#!/bin/bash
# Deploy the RDR2 "missing lines" run to laptop / vm4 / vm5 (3 providers each).
#
# The old C:\rdrw dirs were cleaned when the first RDR2 run finished, so this re-deploys
# EVERYTHING a stream needs -- worker + provider adapter + keys + shard + run3.bat + the
# SYSTEM task. Two rules from CLAUDE.md that this script exists to honour:
#   * only a `.bat` doing `start "" /B python -u worker <prov>`, launched by a SYSTEM
#     scheduled task, survives in session 0. A process launched over ssh dies with the
#     session, and Invoke-CimMethod/Start-Process from a SYSTEM task silently leave
#     nothing running.
#   * the keys live on the machine already (Skyrim's C:\skyrimw\keys.json) -- copy them
#     locally on the box instead of shipping secrets over again.
set -u
KEY=~/.ssh/id_ed25519
H=10.0.0.49
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/rdr2/fleet"
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45 -o ServerAliveInterval=10"

deploy() { # $1 label  $2 port  $3 user
  local L=$1 P=$2 U=$3
  echo "=== $L ==="
  ssh $SSHO -p "$P" "$U@$H" 'if not exist C:\rdrw mkdir C:\rdrw' 2>/dev/null
  # worker + adapter
  scp $SSHO -P "$P" "$FLEET/rdr2_nim.py" "$FLEET/fleet_providers.py" "$U@$H:C:/rdrw/" 2>/dev/null
  # this machine's three shards, named as the worker expects
  for prov in groq sambanova nim; do
    scp $SSHO -P "$P" "$FLEET/shards_missing/corpus_${L}_${prov}.json" \
        "$U@$H:C:/rdrw/corpus_${prov}.json" 2>/dev/null
  done
  # keys: reuse the ones already on the box
  ssh $SSHO -p "$P" "$U@$H" 'copy /Y C:\skyrimw\keys.json C:\rdrw\keys.json' 2>/dev/null | tr -d '\r'
  # the ONE launcher form that persists under a SYSTEM task
  ssh $SSHO -p "$P" "$U@$H" 'powershell -NoProfile -Command "Set-Content -Encoding ASCII C:\rdrw\run3.bat @(''@echo off'',''cd /d C:\rdrw'',''start \"\" /B py.exe -u rdr2_nim.py groq  >> w_groq.log 2>&1'',''start \"\" /B py.exe -u rdr2_nim.py sambanova >> w_sambanova.log 2>&1'',''start \"\" /B py.exe -u rdr2_nim.py nim >> w_nim.log 2>&1'')"' 2>/dev/null
  ssh $SSHO -p "$P" "$U@$H" 'schtasks /create /tn RdrMissing /tr "cmd /c C:\rdrw\run3.bat" /sc minute /mo 5 /ru SYSTEM /rl HIGHEST /f' 2>/dev/null | tr -d '\r' | tail -1
  ssh $SSHO -p "$P" "$U@$H" 'schtasks /run /tn RdrMissing' 2>/dev/null | tr -d '\r' | tail -1
}

deploy laptop 22   Nehoray_Cohen
deploy vm4    2225 vboxuser
deploy vm5    2226 vboxuser
echo "done"
