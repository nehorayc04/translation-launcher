#!/bin/bash
# Crimson Desert -- SELF-HOSTED POOL pull. Supersedes pull_cd.sh for this game: since the
# 2026-08-13 one-pool migration, cd_worker.py clients submit straight to the pool (not to
# per-machine out_*.json), so pull_cd.sh's SCP+reslice path reads stale/empty banks and its
# auto-reslice logic operates on dead local state. This script does exactly what the pool
# architecture needs: keep the live-progress pusher alive, then pull collected pool results
# into fleet/hebrew.json via cc_pull_selfhost.py (QA-gated, same as every other pool puller).

set -u
FLEET="/c/Users/Nehoray_Cohen/Projects/Game translator/games/crimson_desert/fleet"
PY="/c/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"
LPY='C:\Users\Nehoray_Cohen\Projects\Game translator\.venv\Scripts\python.exe'
LOG=/c/tmp/cd_pull_pool.log
LOCK=/c/tmp/cd_pull_pool.lock

if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 240 ] && exit 0
fi
touch "$LOCK"

# keep the live-progress pusher alive (same singleton pattern pull_cd.sh used)
MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -Command "\$ps=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | ?{\$_.CommandLine -match 'cd_progress'} | Sort-Object CreationDate); if (\$ps.Count -eq 0) { Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='\"$LPY\" -u cd_progress.py'; CurrentDirectory='$(cygpath -w "$FLEET")'} | Out-Null } elseif (\$ps.Count -gt 1) { \$ps | Select-Object -Skip 1 | %{ Stop-Process -Id \$_.ProcessId -Force -EA SilentlyContinue } }" >/dev/null 2>&1

cd "$FLEET" && "$PY" cc_pull_selfhost.py --apply >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') pull done" >> "$LOG"
rm -f "$LOCK"
