#!/usr/bin/env bash
set -o pipefail
cd "c:/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"

echo "[brand] === start $(date +%H:%M:%S) ==="
"$PY" det_brand_fix.py 2>&1 | tee brandfix.log

if [ "$(cat brandfix_onscreens.flag 2>/dev/null)" = "1" ]; then
  echo "[brand] re-baking onscreens"
  "$PY" rebuild_onscreens_and_pack.py 2>&1 | tail -n 5
fi
if [ -s brandfix_subs.txt ]; then
  echo "[brand] re-baking $(grep -c . brandfix_subs.txt) subtitle sections"
  "$PY" rebuild_subtitles_and_pack.py --sections-file brandfix_subs.txt 2>&1 | tail -n 4
fi

echo "[brand] === verify re-scan $(date +%H:%M:%S) ==="
"$PY" scan_word_anomalies.py 2>&1 | grep -E "mixed_script_word|long_latin_run|corrupt"
"$PY" scan_language_report.py 2>&1 | grep -E "english_only|foreign_script|corrupt_midword"
echo "[brand] ALL DONE $(date +%H:%M:%S)"
