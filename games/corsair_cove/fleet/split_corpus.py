"""Split corpus.json into one DISJOINT shard per (machine, provider) stream.

WHY A PER-PROVIDER FILE AND NOT `md5(key) % 3`
    A hash split is a FIXED assignment, so the moment one provider is rate-limited its third
    falls behind while the other two finish and their workers EXIT — measured at 68% of the
    remaining work stranded on the slowest stream (Witcher 3). `cc_nim.py` therefore prefers
    `corpus_<provider>.json` and skips the hash filter entirely when it exists.

    It also sidesteps the arithmetic trap: with `md5 % 9`, `md5 % 3` is fully determined by the
    shard index, so 2 of every 3 providers on a machine would get ZERO lines.

ROUND-ROBIN OVER THE VISIBILITY ORDER
    corpus.json is already ordered UI -> dialogue, so dealing the lines out one at a time gives
    every shard the SAME visibility mix (and each shard stays internally ordered). No stream
    ends up holding "all the boring tail".

    python split_corpus.py                 write shards/ for the default 9 streams
    python split_corpus.py vm vm2          only these machines
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.json")
SHARDS = os.path.join(HERE, "shards")

MACHINES = ["vm", "vm2", "vm3"]          # streams 13-21 (local VirtualBox, 127.0.0.1:2222-4)
PROVIDERS = ["groq", "sambanova", "nim"]


def main(argv) -> int:
    machines = [m for m in argv if not m.startswith("-")] or MACHINES
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    streams = [(m, p) for m in machines for p in PROVIDERS]
    n = len(streams)
    buckets = {s: {} for s in streams}
    for i, (k, v) in enumerate(corpus.items()):
        buckets[streams[i % n]][k] = v

    os.makedirs(SHARDS, exist_ok=True)
    total = 0
    for (m, p), d in buckets.items():
        path = os.path.join(SHARDS, f"corpus_{m}_{p}.json")
        json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        total += len(d)
        ui = sum(1 for v in d.values() if v.get("sec") == "ui")
        print(f"  {m:<4} {p:<10} {len(d):>6,} lines   (ui {ui:,} · subs {len(d) - ui:,})")

    # disjointness + completeness are the two properties a reslice must never break
    seen = set()
    dup = 0
    for d in buckets.values():
        for k in d:
            if k in seen: dup += 1
            seen.add(k)
    print(f"\n  {n} streams · {total:,} lines · duplicates {dup} · covers "
          f"{len(seen):,}/{len(corpus):,}")
    return 0 if (dup == 0 and len(seen) == len(corpus)) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
