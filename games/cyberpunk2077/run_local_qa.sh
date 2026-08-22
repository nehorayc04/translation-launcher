#!/usr/bin/env bash
set -o pipefail
cd "c:/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"
DIR="${1:-qa_batches_local}"
echo "[lqa] === local-model semantic QA start $(date +%H:%M:%S) dir=$DIR ==="
"$PY" local_semantic_qa.py "$DIR" 2>&1 | tee local_qa.log
if [ "$(cat local_semantic_onscreens.flag 2>/dev/null)" = "1" ]; then
  echo "[lqa] re-baking onscreens"
  "$PY" rebuild_onscreens_and_pack.py 2>&1 | tail -n 4
fi
if [ -s local_semantic_subs.txt ]; then
  echo "[lqa] re-baking $(grep -c . local_semantic_subs.txt) subtitle sections"
  "$PY" rebuild_subtitles_and_pack.py --sections-file local_semantic_subs.txt 2>&1 | tail -n 3
fi
echo "[lqa] verify"
"$PY" - <<'PYEOF'
import sys, os, json, collections
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join('..', '..', 'universal'))
import cp2077_qa_sweep as S, cp2077_qa_defects as Q
tr = json.load(open(S.TRANSLATED_FILE, encoding='utf-8'))
ex = json.load(open(S.EXPORT_FILE, encoding='utf-8'))
print('  canonical:', dict(collections.Counter(d.kind for d in Q.scan_all(tr, ex))))
PYEOF
echo "[lqa] ALL DONE $(date +%H:%M:%S)"
