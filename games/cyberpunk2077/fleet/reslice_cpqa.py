# -*- coding: utf-8 -*-
"""Reslice the UNDONE CP2077 QA corpus across the surviving streams (default 2: vm4, laptop)
after VM1 is paused. Reads qa_corpus.json + all banks/out_*.json (done), splits the remainder
md5(id)%N into splits/reslice_<i>.json. Each survivor gets one; its own out.json is KEPT."""
import json, os, sys, hashlib, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "qa_corpus.json")
BANKS = os.path.join(HERE, "banks")
OUTDIR = os.path.join(HERE, "splits")


def main(n=2):
    os.makedirs(OUTDIR, exist_ok=True)
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    done = set()
    for f in glob.glob(os.path.join(BANKS, "out_*.json")) + [os.path.join(HERE, "cpqa_out.json")]:
        try:
            for k, v in json.load(open(f, encoding="utf-8")).items():
                if isinstance(v, dict) and isinstance(v.get("he"), str):
                    done.add(k)
        except Exception:
            pass
    undone = {k: v for k, v in corpus.items() if k not in done}
    parts = [{} for _ in range(n)]
    for k, v in undone.items():
        parts[int(hashlib.md5(k.encode()).hexdigest(), 16) % n][k] = v
    for i, p in enumerate(parts):
        f = os.path.join(OUTDIR, f"reslice_{i}.json")
        json.dump(p, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"reslice_{i}.json: {len(p)}")
    print(f"corpus {len(corpus)}  done {len(done)}  undone {len(undone)} -> {n} slices")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
