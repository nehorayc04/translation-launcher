#!/usr/bin/env bash
set -o pipefail
cd "c:/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"
echo "[res] === start $(date +%H:%M:%S) ==="
"$PY" det_residual_fix.py 2>&1 | tee residfix.log
if [ "$(cat residfix_onscreens.flag 2>/dev/null)" = "1" ]; then
  echo "[res] re-baking onscreens"
  "$PY" rebuild_onscreens_and_pack.py 2>&1 | tail -n 4
fi
if [ -s residfix_subs.txt ]; then
  echo "[res] re-baking $(grep -c . residfix_subs.txt) subtitle sections"
  "$PY" rebuild_subtitles_and_pack.py --sections-file residfix_subs.txt 2>&1 | tail -n 3
fi
echo "[res] === verify $(date +%H:%M:%S) ==="
"$PY" - <<'PYEOF'
import sys, os, json, collections
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join('..', '..', 'universal'))
import cp2077_qa_sweep as S, cp2077_qa_defects as Q
tr = json.load(open(S.TRANSLATED_FILE, encoding='utf-8'))
ex = json.load(open(S.EXPORT_FILE, encoding='utf-8'))
c = collections.Counter(d.kind for d in Q.scan_all(tr, ex))
print('  canonical:', dict(c))
PYEOF
"$PY" scan_language_report.py 2>&1 | grep -E "english_only|foreign_script|corrupt_midword"
echo "[res] ALL DONE $(date +%H:%M:%S)"
