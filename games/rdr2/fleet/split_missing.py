#!/usr/bin/env python3
"""Split corpus_missing.json into one disjoint shard per machine x provider.

Round-robin over the VISIBILITY-ordered corpus, so every shard gets the same mix of
UI-first / dialogue-later work and no stream ends up holding only the boring tail
([[fleet-equal-reslice]]).
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MACHINES = ["laptop", "vm4", "vm5"]
PROVIDERS = ["groq", "sambanova", "nim"]


def main() -> None:
    corpus = json.load(open(os.path.join(HERE, "corpus_missing.json"), encoding="utf-8"))
    keys = list(corpus)                       # already visibility-ordered
    streams = [(m, p) for m in MACHINES for p in PROVIDERS]
    shards = {s: {} for s in streams}
    for i, k in enumerate(keys):
        shards[streams[i % len(streams)]][k] = corpus[k]

    out = os.path.join(HERE, "shards_missing")
    os.makedirs(out, exist_ok=True)
    seen = set()
    for (m, p), d in shards.items():
        with open(os.path.join(out, f"corpus_{m}_{p}.json"), "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        assert not (seen & set(d)), "shards overlap"
        seen |= set(d)
        print(f"  {m:<8} {p:<10} {len(d):,}")
    assert seen == set(keys), "shards do not cover the corpus"
    print(f"\n{len(streams)} streams, {len(seen):,} lines, disjoint and complete")


if __name__ == "__main__":
    main()
