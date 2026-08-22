# -*- coding: utf-8 -*-
"""sample_round.py — build the NEXT disjoint batch of translatable prose lines
for the semantic QA workflow. Tracks every line ever sampled in used_keys.json
so successive rounds never overlap. Deterministic corpus order (no RNG).

Usage: python sample_round.py <count> <out_dir>
Writes <out_dir>/batch_NN.json (10 lines each) + grows used_keys.json."""
import os, sys, json, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
try:
    import smart_filter_queue as SF
except Exception:
    SF = None

HEB = re.compile(r"[א-ת]")
USED = os.path.join(HERE, "used_keys.json")


def bucket(sec):
    if sec.startswith("onscreens"):
        return "onscreens"
    if sec.startswith("subtitles/quest"):
        return "quest"
    if sec.startswith("subtitles/open_world/voicesets"):
        return "voiceset"
    if sec.startswith("subtitles"):
        return "subtitle_other"
    return "other"


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 140
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "qa_batches_next"
    os.makedirs(os.path.join(HERE, out_dir), exist_ok=True)

    used = set()
    if os.path.exists(USED):
        used = set(json.load(open(USED, encoding="utf-8")))
    # also seed from the first two manual rounds so we never re-pick them
    for fn in ("quality_sample.json", "quality_sample2.json"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            for r in json.load(open(p, encoding="utf-8")):
                used.add(f"{r['section']}|{r['pk']}|{r['field']}")

    corpus, _, _ = G.build_corpus()
    # stratified round-robin across buckets for a representative mix
    pools = collections.defaultdict(list)
    for r in corpus:
        sec = r.section
        if sec.startswith("ep1"):
            continue
        he = r.hebrew or ""; en = r.english or ""
        if not he.strip() or not en.strip() or not HEB.search(he):
            continue
        if len(HEB.findall(he)) < 8 or len(en) < 25:
            continue
        key = f"{sec}|{r.pk}|{r.field}"
        if key in used:
            continue
        pools[bucket(sec)].append({"section": sec, "pk": str(r.pk), "field": r.field,
                                   "hebrew": he[:400], "english": en[:400], "key": key})

    order = ["quest", "onscreens", "voiceset", "subtitle_other", "other"]
    picks, idx = [], {b: 0 for b in order}
    while len(picks) < count and any(idx[b] < len(pools.get(b, [])) for b in order):
        for b in order:
            p = pools.get(b, [])
            if idx[b] < len(p) and len(picks) < count:
                picks.append(p[idx[b]]); idx[b] += 1

    for x in picks:
        used.add(x["key"])
    json.dump(sorted(used), open(USED, "w", encoding="utf-8"), ensure_ascii=False)

    B = 10
    nb = 0
    for i in range(0, len(picks), B):
        batch = [{"idx": j, "section": r["section"], "pk": r["pk"], "field": r["field"],
                  "hebrew": r["hebrew"], "english": r["english"]} for j, r in enumerate(picks[i:i + B], i)]
        json.dump(batch, open(os.path.join(HERE, out_dir, f"batch_{i // B:02d}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        nb += 1
    print(f"sampled {len(picks)} fresh lines -> {out_dir} ({nb} batches); used total {len(used)}")
    print("bucket spread:", {b: len(pools.get(b, [])) for b in order})


if __name__ == "__main__":
    main()
