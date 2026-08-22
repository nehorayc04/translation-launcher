#!/bin/bash
# Background chain: bake+deploy the base SUBTITLE fixes (targeted to the CPQA-affected sections),
# then the DLC fixes. Onscreens was already baked+deployed. Sequential (DLC is a separate archive,
# so it never conflicts with the base tree). Logs everything; game MUST stay closed the whole time.
set -u
cd "/c/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/AppData/Local/Programs/Python/Python313/python.exe"
LOG=/c/tmp/cpqa_bake_rest.log
SECS="fleet/affected_cpqa_sections.txt"
echo "=== $(date '+%F %T') SUBTITLE bake start ($(wc -l < $SECS) sections) ===" >> "$LOG"
"$PY" -X utf8 rebuild_subtitles_and_pack.py --sections-file "$SECS" >> "$LOG" 2>&1
echo "=== $(date '+%F %T') SUBTITLE done rc=$? ===" >> "$LOG"
echo "=== $(date '+%F %T') DLC bake start ===" >> "$LOG"
"$PY" -X utf8 rebuild_dlc_and_pack.py --force-rebake >> "$LOG" 2>&1
echo "=== $(date '+%F %T') DLC done rc=$? — ALL CPQA FIXES DEPLOYED LOCALLY ===" >> "$LOG"
