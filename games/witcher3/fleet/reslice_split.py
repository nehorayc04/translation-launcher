"""Re-slice the REMAINING (not-yet-banked) W3 keys into 6 disjoint, length-balanced slices —
one per stream (vm, vm2, vm4, vm5, laptop, desktop) — so the heavy long-narrative tail is done in
parallel with ZERO overlap instead of all 6 redundantly chewing the same keys. Gender-aware {en,ar}.
out.json on each stream is KEPT (already-done keys just get skipped)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew.json")
FULL = os.path.join(HERE, "desktop_worker", "corpus.json")   # full gender-aware {k:{en,ar}}
STREAMS = ["vm", "vm2", "vm4", "vm5", "laptop", "desktop"]

def en(v): return (v.get("en") if isinstance(v, dict) else v) or ""

bank = json.load(open(BANK, encoding="utf-8"))
full = json.load(open(FULL, encoding="utf-8"))

def banked(k):
    v = bank.get(k)
    return isinstance(v, str) and v.strip() != ""

rem = [k for k in full if not banked(k)]
# sort by EN length DESC, round-robin into 6 bins => each bin gets a balanced mix of long+short
rem.sort(key=lambda k: -len(en(full[k])))
bins = {s: {} for s in STREAMS}
load = {s: 0 for s in STREAMS}
for k in rem:
    s = min(STREAMS, key=lambda x: load[x])   # give next (longest-remaining) key to the lightest bin
    bins[s][k] = full[k]
    load[s] += len(en(full[k]))

print(f"remaining to re-slice: {len(rem)}")
for s in STREAMS:
    n = len(bins[s]); chars = load[s]
    out = os.path.join(HERE, f"reslice_{s}.json")
    json.dump(bins[s], open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  {s:8s} keys={n:5d} chars={chars:8d} -> {os.path.basename(out)}")
# sanity: disjoint + complete
allk = set()
for s in STREAMS: allk |= set(bins[s])
assert len(allk) == len(rem) == sum(len(bins[s]) for s in STREAMS), "SPLIT NOT DISJOINT/COMPLETE"
print("OK: 6 slices are disjoint and cover all remaining keys.")
