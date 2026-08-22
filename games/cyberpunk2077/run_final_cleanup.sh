#!/usr/bin/env bash
set -o pipefail
cd "c:/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"

echo "[final] === cleanup pass start $(date +%H:%M:%S) ==="
"$PY" final_cleanup.py 2>&1 | tee final_cleanup.log

ONS=$(cat final_cleanup_onscreens.flag 2>/dev/null)
if [ "$ONS" = "1" ]; then
  echo "[final] re-baking onscreens"
  "$PY" rebuild_onscreens_and_pack.py 2>&1 | tail -n 6
fi

if [ -s final_cleanup_subs.txt ]; then
  N=$(grep -c . final_cleanup_subs.txt)
  echo "[final] re-baking $N touched subtitle sections"
  "$PY" rebuild_subtitles_and_pack.py --sections-file final_cleanup_subs.txt 2>&1 | tail -n 4
else
  echo "[final] no subtitle sections touched"
fi

echo "[final] === re-scan $(date +%H:%M:%S) ==="
"$PY" scan_word_anomalies.py 2>&1 | tail -n 16
echo "--- language ---"
"$PY" scan_language_report.py 2>&1 | tail -n 6
echo "[final] ALL DONE $(date +%H:%M:%S)"
