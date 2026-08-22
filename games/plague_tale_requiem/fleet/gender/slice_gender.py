#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split gender_corpus.json into disjoint slices for the free fleet streams.
Usage: python slice_gender.py vm vm2 desktop
Writes gslice_<stream>.json (one per stream), disjoint + covering all keys.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    streams = sys.argv[1:] or ["vm", "vm2", "desktop"]
    corpus = json.load(open(os.path.join(HERE, "gender_corpus.json"), encoding="utf-8"))
    keys = list(corpus.keys())
    # longest-first round-robin -> balanced token load
    keys.sort(key=lambda k: -(len(corpus[k].get("en", "")) + len(corpus[k].get("ar", "")) + len(corpus[k].get("he", ""))))
    buckets = {s: {} for s in streams}
    for i, k in enumerate(keys):
        buckets[streams[i % len(streams)]][k] = corpus[k]
    seen = set()
    for s in streams:
        p = os.path.join(HERE, f"gslice_{s}.json")
        json.dump(buckets[s], open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        assert not (seen & buckets[s].keys()), "overlap!"
        seen |= buckets[s].keys()
        print(f"  {s:8s} {len(buckets[s]):5d} -> {p}")
    assert seen == set(keys), "coverage gap!"
    print(f"OK: {len(streams)} disjoint slices cover all {len(keys)} reviewable keys.")


if __name__ == "__main__":
    main()
