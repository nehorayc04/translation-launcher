#!/bin/bash
# CLEAN single CP2077 full re-bake on the QUALITY-FIXED spine. A lock prevents a second
# concurrent bake (the earlier double-bake caused rc=127 + an uncertain archive).
# onscreens (always fresh) -> subtitles --all (force) -> DLC --force-rebake (was stale/pre-dual-gender).
LOCK=/c/tmp/cp2077_bake.lock
if [ -f "$LOCK" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$age" -lt 600 ] && { echo "another bake holds the lock (age ${age}s) — abort"; exit 3; }
fi
echo $$ > "$LOCK"
cd "/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="/c/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LOG=/c/tmp/cp2077_bg_bake.log
touch_lock(){ while true; do echo $$ > "$LOCK"; sleep 60; done; }
touch_lock & TK=$!
{
  echo "===== CLEAN FULL BAKE (fixed spine) START $(date '+%F %T') ====="
  echo "----- ONSCREENS $(date '+%T') -----";           "$PY" -u rebuild_onscreens_and_pack.py;      echo "----- ONSCREENS rc=$? -----"
  echo "----- SUBTITLES --all $(date '+%T') -----";      "$PY" -u rebuild_subtitles_and_pack.py --all; echo "----- SUBTITLES rc=$? -----"
  echo "----- DLC --force-rebake $(date '+%T') -----";   "$PY" -u rebuild_dlc_and_pack.py --force-rebake; echo "----- DLC rc=$? -----"
  echo "===== CLEAN FULL BAKE COMPLETE $(date '+%F %T') ====="
} >> "$LOG" 2>&1
kill "$TK" 2>/dev/null; rm -f "$LOCK"
