#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice the REMAINING (not-yet-reviewed) gender-review keys across the given streams.
Remaining = gender_corpus.json keys NOT present in any gbanks/out_*.json (already reviewed).
Usage: python slice_gender_remaining.py vm3 vm4 vm5 laptop
Writes gslice_<stream>.json (disjoint, covering all remaining).
"""
import json, os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    streams = sys.argv[1:] or ["vm3", "vm4", "vm5", "laptop"]
    corpus = json.load(open(os.path.join(HERE, "gender_corpus.json"), encoding="utf-8"))
    reviewed = set()
    for f in glob.glob(os.path.join(HERE, "gbanks", "out_*.json")):
        try:
            reviewed |= set(json.load(open(f, encoding="utf-8")).keys())
        except Exception:
            pass
    rem = [k for k in corpus if k not in reviewed]
    rem.sort(key=lambda k: -(len(corpus[k].get("en", "")) + len(corpus[k].get("ar", "")) + len(corpus[k].get("he", ""))))
    buckets = {s: {} for s in streams}
    for i, k in enumerate(rem):
        buckets[streams[i % len(streams)]][k] = corpus[k]
    seen = set()
    for s in streams:
        p = os.path.join(HERE, f"gslice_{s}.json")
        json.dump(buckets[s], open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        assert not (seen & buckets[s].keys())
        seen |= buckets[s].keys()
        print(f"  {s:8s} {len(buckets[s]):5d} -> {p}")
    print(f"OK: corpus={len(corpus)} already-reviewed={len(reviewed)} remaining={len(rem)} across {len(streams)} streams")


if __name__ == "__main__":
    main()
