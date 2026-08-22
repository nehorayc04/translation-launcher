#!/usr/bin/env bash
# Comprehensive multi-angle QA battery. Runs the canonical audit->fix->re-audit
# loop on the REAL fixable defect classes (foreign + english_leak), bakes the
# touched sections, then re-scans from every angle and prints a consolidated
# count. Safe to run again and again (converges; gemma-gated, brand-aware).
set -o pipefail
cd "c:/Users/Nehoray_Cohen/Projects/Game translator/games/cyberpunk2077" || exit 1
PY="C:/Users/Nehoray_Cohen/Projects/Game translator/.venv/Scripts/python.exe"

echo "[qa] ===== battery start $(date +%H:%M:%S) ====="

echo "[qa] angle-1: canonical audit -> fix -> re-audit (foreign + english_leak)"
"$PY" cp2077_qa_sweep.py --only foreign,english_leak --max-iterations 5 2>&1 | tail -n 18

echo "[qa] collecting touched sections"
"$PY" - <<'PYEOF'
import json
try:
    rep = json.load(open('qa_sweep_report.json', encoding='utf-8'))
except Exception:
    rep = {}
ps = rep.get('patched_sections', {})
ons = ps.get('onscreens', []); subs = ps.get('subtitles', [])
open('qa_bake_subs.txt', 'w', encoding='utf-8').write('\n'.join(subs))
open('qa_bake_ons.flag', 'w').write('1' if ons else '0')
print(f'  touched onscreens={len(ons)} subtitles={len(subs)}')
PYEOF

if [ "$(cat qa_bake_ons.flag 2>/dev/null)" = "1" ]; then
  echo "[qa] re-baking onscreens"
  "$PY" rebuild_onscreens_and_pack.py 2>&1 | tail -n 4
fi
if [ -s qa_bake_subs.txt ]; then
  echo "[qa] re-baking $(grep -c . qa_bake_subs.txt) subtitle sections"
  "$PY" rebuild_subtitles_and_pack.py --sections-file qa_bake_subs.txt 2>&1 | tail -n 3
fi

echo "[qa] angle-2: canonical scan_all (slot-aware)"
"$PY" - <<'PYEOF'
import sys, os, json, collections
sys.path.insert(0, '.'); sys.path.insert(0, os.path.join('..', '..', 'universal'))
import cp2077_qa_sweep as S, cp2077_qa_defects as Q
tr = json.load(open(S.TRANSLATED_FILE, encoding='utf-8'))
ex = json.load(open(S.EXPORT_FILE, encoding='utf-8'))
c = collections.Counter(d.kind for d in Q.scan_all(tr, ex))
print('  canonical:', dict(c))
PYEOF

echo "[qa] angle-3: word anomalies"
"$PY" scan_word_anomalies.py 2>&1 | grep -E "mixed_script_word|corrupt|long_latin_run|hebrew_too_long"
echo "[qa] angle-4: language scan"
"$PY" scan_language_report.py 2>&1 | grep -E "english_only|foreign_script|corrupt_midword"

echo "[qa] ===== battery DONE $(date +%H:%M:%S) ====="
