#!/usr/bin/env python3
"""Re-slice whatever is LEFT of the missing-lines corpus across every available stream.

Union the banks, take the remainder IN CORPUS ORDER (which is visibility-ordered, so no
shard ends up holding only the boring tail), and round-robin it across machine x provider.
Re-runnable: it recomputes from the banks, so a stream dying mid-shard costs nothing.

⚠️ The number of MACHINE slices must not be a multiple of 3 in the worker's own md5%3
fallback -- irrelevant here because every stream gets an explicit corpus_<provider>.json,
which overrides that split entirely.
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    machines = sys.argv[1:] or ["laptop", "vm4", "vm5"]
    providers = ["groq", "sambanova", "nim"]

    corpus = json.load(open(os.path.join(HERE, "corpus_missing.json"), encoding="utf-8"))
    done = set()
    for f in glob.glob(os.path.join(HERE, "banks_missing", "out_*.json")):
        try:
            done |= set(json.load(open(f, encoding="utf-8")))
        except Exception:
            pass
    # ALSO exclude what the MERGE already resolved (deterministic ordinal fills, name-canon)
    # — those never appear in a worker's out_*.json, so a bank-only `done` re-served them and
    # every stream burned singleton retries re-deriving an answer the merge overwrites anyway.
    try:
        done |= set(json.load(open(os.path.join(HERE, "hebrew_missing.json"), encoding="utf-8")))
    except Exception:
        pass

    todo = [k for k in corpus if k not in done]

    # 🔴 EASY-FIRST, not corpus order. The remainder is by definition what REPEATEDLY failed,
    # so a round-robin that preserves corpus order lands the same hard cluster at the FRONT of
    # all 21 shards at once and the whole fleet crawls behind it (the documented Skyrim
    # book-cluster stall). A stable sort by a cheap hardness proxy — token count, then length —
    # puts the quick wins first; the hard tail still gets translated, just last, and by then it
    # is spread thin instead of blocking every stream simultaneously.
    def _hardness(k):
        v = corpus[k]
        s = (v.get("en", "") if isinstance(v, dict) else str(v or ""))
        return (s.count("~") + s.count("[") + s.count("%"), len(s))

    todo.sort(key=_hardness)

    streams = [(m, p) for m in machines for p in providers]
    shards = {s: {} for s in streams}
    for i, k in enumerate(todo):
        shards[streams[i % len(streams)]][k] = corpus[k]

    out = os.path.join(HERE, "shards_missing")
    os.makedirs(out, exist_ok=True)
    for (m, p), d in shards.items():
        with open(os.path.join(out, f"corpus_{m}_{p}.json"), "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)

    print(f"banked {len(done):,} / {len(corpus):,}   remaining {len(todo):,}")
    print(f"{len(streams)} streams x ~{len(todo)//max(len(streams),1):,} lines")


if __name__ == "__main__":
    main()
