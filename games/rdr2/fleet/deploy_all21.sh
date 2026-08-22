#!/bin/bash
# Push the re-sliced shards to all 7 machines and restart every RDR2 worker.
#
# Workers read their corpus ONCE at startup, so a reslice is always deploy-shards +
# RESTART -- and the restart must go through the machine's SYSTEM task, because a worker
# launched over ssh dies with the session. The desktop is local, where a detached
# Start-Process does persist.
set -u
KEY=~/.ssh/id_ed25519
FLEET="$(cd "$(dirname "$0")" && pwd)"
SH="$FLEET/shards_missing"
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=45"

push() { # $1 label  $2 host  $3 port  $4 user  $5 remote-dir  $6 python
  local L=$1 HOST=$2 P=$3 U=$4 D=$5 PY=$6
  echo "=== $L ==="
  ssh $SSHO -p "$P" "$U@$HOST" "if not exist $D mkdir $D" 2>/dev/null
  scp $SSHO -P "$P" "$FLEET/rdr2_nim.py" "$FLEET/fleet_providers.py" \
      "$FLEET/name_registry.json" "$FLEET/name_fixes.json" "$U@$HOST:${D//\\//}/" 2>/dev/null
  for prov in groq sambanova nim; do
    scp $SSHO -P "$P" "$SH/corpus_${L}_${prov}.json" "$U@$HOST:${D//\\//}/corpus_${prov}.json" 2>/dev/null
  done
  # keys: reuse whatever this box already has
  ssh $SSHO -p "$P" "$U@$HOST" "if not exist $D\\keys.json (copy /Y C:\\skyrimw\\keys.json $D\\keys.json)" 2>/dev/null >/dev/null
  # launcher (the only form that survives in session 0)
  ssh $SSHO -p "$P" "$U@$HOST" "powershell -NoProfile -Command \"'@echo off','cd /d %~dp0','start \\\"\\\" /B \\\"$PY\\\" -u rdr2_nim.py groq >> w_groq.log 2>&1','start \\\"\\\" /B \\\"$PY\\\" -u rdr2_nim.py sambanova >> w_sambanova.log 2>&1','start \\\"\\\" /B \\\"$PY\\\" -u rdr2_nim.py nim >> w_nim.log 2>&1' | Set-Content -Encoding ASCII $D\\run3.bat\"" 2>/dev/null
  # kill the old workers (they hold the singleton lock AND the previous shard) then relaunch
  ssh $SSHO -p "$P" "$U@$HOST" 'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name=`\"python.exe`\"\" | Where-Object CommandLine -match rdr2_nim | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }"' 2>/dev/null
  ssh $SSHO -p "$P" "$U@$HOST" "schtasks /create /tn RdrMissing /tr \"cmd /c $D\\run3.bat\" /sc minute /mo 5 /ru SYSTEM /rl HIGHEST /f" 2>/dev/null >/dev/null
  ssh $SSHO -p "$P" "$U@$HOST" 'schtasks /run /tn RdrMissing' 2>/dev/null | tr -d '\r' | tail -1
}

VMPY='C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
LAPPY='C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'

push laptop 10.0.0.49 22   Nehoray_Cohen 'C:\rdrw' "$LAPPY"
push vm4    10.0.0.49 2225 vboxuser      'C:\rdrw' "$VMPY"
push vm5    10.0.0.49 2226 vboxuser      'C:\rdrw' "$VMPY"
push vm     127.0.0.1 2222 vboxuser      'C:\rdrw' "$VMPY"
push vm2    127.0.0.1 2223 vboxuser      'C:\rdrw' "$VMPY"
push vm3    127.0.0.1 2224 vboxuser      'C:\rdrw' "$VMPY"
echo done
