"""Re-slice the REMAINING (not-yet-banked) PT Requiem keys into N disjoint, length-balanced
slices — one per ACTIVE stream — so the tail is done in parallel with ZERO overlap. Gender-aware
{en,ar}. out.json on each stream is KEPT (already-done keys just get skipped).

FULL corpus = the master extract/gender_source.json (all 20,661, {en,ar,hint} -> {en,ar}).
BANK = fleet/hebrew.json (everything pulled+merged so far).

Usage:  python reslice_split.py [stream1 stream2 ...]
        (default = the 4 active streams: vm3 vm4 vm5 laptop; desktop/vm/vm2 are on the W3 loan)
Writes reslice_<stream>.json per given stream; deploy with reslice_deploy.sh.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew.json")
MASTER = os.path.join(HERE, "..", "extract", "gender_source.json")   # {k:{en,ar,hint}} — full 20,661
SPLITS = os.path.join(HERE, "splits")

DEFAULT_STREAMS = ["vm3", "vm4", "vm5", "laptop"]
STREAMS = sys.argv[1:] or DEFAULT_STREAMS


def en(v):
    return (v.get("en") if isinstance(v, dict) else v) or ""


def load_full():
    """Prefer the authoritative master; fall back to the union of the current 7 splits."""
    if os.path.exists(MASTER):
        raw = json.load(open(MASTER, encoding="utf-8"))
        return {k: {"en": (v.get("en") if isinstance(v, dict) else v) or "",
                    "ar": (v.get("ar") if isinstance(v, dict) else "") or ""}
                for k, v in raw.items()}
    full = {}
    for f in os.listdir(SPLITS):
        if f.startswith("corpus_pt_") and f.endswith(".json"):
            for k, v in json.load(open(os.path.join(SPLITS, f), encoding="utf-8")).items():
                full.setdefault(k, {"en": en(v), "ar": (v.get("ar") if isinstance(v, dict) else "") or ""})
    return full


bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else {}
full = load_full()
try:
    MARKERS = set(json.load(open(os.path.join(HERE, "marker_keys.json"), encoding="utf-8")))
except Exception:
    MARKERS = set()


def banked(k):
    v = bank.get(k)
    return isinstance(v, str) and v.strip() != ""


rem = [k for k in full if not banked(k) and k not in MARKERS]   # skip non-translatable markers
# longest-remaining EN first, always to the lightest bin => balanced long+short mix per stream
rem.sort(key=lambda k: -len(en(full[k])))
bins = {s: {} for s in STREAMS}
load = {s: 0 for s in STREAMS}
for k in rem:
    s = min(STREAMS, key=lambda x: load[x])
    bins[s][k] = full[k]
    load[s] += len(en(full[k])) + 1

print(f"master={len(full)}  banked={sum(1 for k in full if banked(k))}  remaining={len(rem)}  streams={STREAMS}")
for s in STREAMS:
    out = os.path.join(HERE, f"reslice_{s}.json")
    json.dump(bins[s], open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  {s:8s} keys={len(bins[s]):5d} chars={load[s]:8d} -> {os.path.basename(out)}")

allk = set()
for s in STREAMS:
    allk |= set(bins[s])
assert len(allk) == len(rem) == sum(len(bins[s]) for s in STREAMS), "SPLIT NOT DISJOINT/COMPLETE"
print(f"OK: {len(STREAMS)} slices are disjoint and cover ALL {len(rem)} remaining keys.")
