#!/bin/bash
# drain_loop.sh — keep 3 disjoint masked-drain slices running until the corpus is covered.
#
# A single drain pass walks its slice ONCE: a batch the provider answers emptily is simply
# skipped, so one pass never reaches 100 %. Re-running is what converges — each new pass
# recomputes `todo` from what is already banked, so it only re-asks what is genuinely left.
# Stops on its own when the remainder stops shrinking twice in a row (the "dry" rule), so a
# genuinely unanswerable line can never spin here forever.
set -u
FLEET="$(cd "$(dirname "$0")" && pwd)"
cd "$FLEET" || exit 1
PY=python
left() {
  $PY - <<'PY'
import json, glob, os
c = json.load(open("corpus_missing.json", encoding="utf-8"))
b = json.load(open("hebrew_missing.json", encoding="utf-8"))
m = set()
for f in glob.glob(os.path.join("banks_missing", "out_zzmask*.json")):
    try:
        m |= set(json.load(open(f, encoding="utf-8")))
    except Exception:
        pass
print(len([k for k in c if k not in b and k not in m]))
PY
}

prev=$(left); dry=0
for round in $(seq 1 12); do
  echo "=== round $round · $prev left ==="
  for i in 0 1 2; do
    $PY drain_tokenheavy.py --apply --min-tokens 0 --slice "$i/3" > "/c/tmp/drain_s$i.log" 2>&1 &
  done
  wait
  now=$(left)
  echo "    $prev -> $now"
  [ "$now" -le 3 ] && { echo "COVERED ($now left)"; break; }
  if [ "$now" -ge "$prev" ]; then
    dry=$((dry + 1))
    [ "$dry" -ge 2 ] && { echo "DRY — $now lines will not translate here"; break; }
  else
    dry=0
  fi
  prev=$now
done
echo "final: $(left) uncovered"
