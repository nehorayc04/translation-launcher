#!/usr/bin/env bash
set -o pipefail
cd "c:/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"
echo "[sem] === apply $(date +%H:%M:%S) ==="
"$PY" apply_semantic_fixes.py 2>&1 | tee apply_semantic.log
if [ "$(cat semantic_onscreens.flag 2>/dev/null)" = "1" ]; then
  echo "[sem] re-baking onscreens"
  "$PY" rebuild_onscreens_and_pack.py 2>&1 | tail -n 4
fi
if [ -s semantic_subs.txt ]; then
  echo "[sem] re-baking $(grep -c . semantic_subs.txt) subtitle sections"
  "$PY" rebuild_subtitles_and_pack.py --sections-file semantic_subs.txt 2>&1 | tail -n 3
fi
echo "[sem] === verify $(date +%H:%M:%S) ==="
"$PY" - <<'PYEOF'
import sys, os, json, collections
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join('..', '..', 'universal'))
import cp2077_qa_sweep as S, cp2077_qa_defects as Q
tr = json.load(open(S.TRANSLATED_FILE, encoding='utf-8'))
ex = json.load(open(S.EXPORT_FILE, encoding='utf-8'))
print('  canonical:', dict(collections.Counter(d.kind for d in Q.scan_all(tr, ex))))
PYEOF
echo "[sem] ALL DONE $(date +%H:%M:%S)"
