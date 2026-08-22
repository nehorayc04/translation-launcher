# -*- coding: utf-8 -*-
"""Split qa_corpus.json into N disjoint slices by md5(id)%N (stable, resumable). Default N=3.
Writes splits/cpqa_<0..N-1>.json. Each stream gets one slice as its corpus.json."""
import json, os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "qa_corpus.json")
OUTDIR = os.path.join(HERE, "splits")


def main(n=3):
    os.makedirs(OUTDIR, exist_ok=True)
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    parts = [{} for _ in range(n)]
    for k, v in corpus.items():
        idx = int(hashlib.md5(k.encode("utf-8")).hexdigest(), 16) % n
        parts[idx][k] = v
    for i, p in enumerate(parts):
        f = os.path.join(OUTDIR, f"cpqa_{i}.json")
        json.dump(p, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"cpqa_{i}.json: {len(p)}")
    print(f"total {sum(len(p) for p in parts)} into {n} disjoint slices")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
