# -*- coding: utf-8 -*-
"""Re-slice a fleet's REMAINING corpus into an EXACTLY equal share per provider-stream.

Why this exists (measured 2026-07-26, W3 QA + CP2077 QA):
  * The workers partition by `md5(key) % 3 == provider_index`. That is fine on a fresh corpus,
    but it is a FIXED assignment: once one provider is rate-limited (groq 429s constantly) its
    third falls behind and the OTHER providers finish and EXIT. Measured W3 remainder by residue:
    groq 5,160 / sambanova 733 / nim 1,674 — i.e. 68% of the work sat on the slowest stream while
    a third of the fleet was idle. CP2077: nim's third was 100% done, groq+sambanova held it all.
  * Machine slices were re-cut over time while OTHER machines kept their older, wider slices, so
    the same key lived in two machines' corpora: 32% of the W3 reviews (39,756 rows) and 27% of
    the CP2077 reviews (76,136) were DUPLICATE work.

This tool fixes both: it unions every bank (what is genuinely reviewed), takes the remainder in
CORPUS ORDER (the corpus is visibility-ordered, so shard 0 is not "all the boring tail"), and
round-robins it across the given streams -> disjoint, equal-size, same visibility mix.

The worker picks the shard up as `corpus_<provider>.json` next to it, which OVERRIDES the md5%3
split (see the `per_prov` branch in w3qa_nim.py / cpqa_nim.py). Re-runnable: it always recomputes
from the banks, so a stream that dies mid-shard loses nothing.

  py universal/fleet_reslice_equal.py <corpus.json> <banks_dir> <bank_glob> <out_dir> m1 m2 ...
  py universal/fleet_reslice_equal.py ... --providers groq,sambanova,nim
"""
import glob
import json
import os
import sys

DEF_PROVIDERS = ["groq", "sambanova", "nim"]


def _load_keys(path):
    """Bank files are {id: verdict}; a union sidecar is a plain list. Accept both."""
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return set(d) if isinstance(d, dict) else set(map(str, d))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 5:
        print(__doc__)
        return 2
    corpus_p, banks_dir, bank_glob, out_dir = a[0], a[1], a[2], a[3]
    machines = a[4:]
    provs = DEF_PROVIDERS
    if "--providers" in sys.argv:
        provs = [p.strip() for p in sys.argv[sys.argv.index("--providers") + 1].split(",") if p.strip()]

    corpus = json.load(open(corpus_p, encoding="utf-8"))
    reviewed, bad = set(), []
    for f in sorted(glob.glob(os.path.join(banks_dir, bank_glob))):
        try:
            reviewed |= _load_keys(f)
        except Exception as e:                                   # a NUL-truncated bank, etc.
            bad.append(f"{os.path.basename(f)}: {e}")
    # corpus order is preserved (dict insertion order == visibility order from build_qa_corpus)
    rem = [k for k in corpus if k not in reviewed]

    print(f"corpus            : {len(corpus)}")
    print(f"reviewed (union)  : {len(reviewed)}")
    print(f"REMAINING         : {len(rem)}")
    if bad:
        print("  unreadable banks: " + "; ".join(bad))
    if not rem:
        print("nothing left to slice.")
        return 0

    streams = [(m, p) for m in machines for p in provs]
    shards = {s: {} for s in streams}
    for i, k in enumerate(rem):                                  # round-robin == equal + same mix
        shards[streams[i % len(streams)]][k] = corpus[k]

    os.makedirs(out_dir, exist_ok=True)
    sizes = []
    for (m, p), d in shards.items():
        out = os.path.join(out_dir, f"corpus_{m}_{p}.json")
        json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        sizes.append(len(d))
        print(f"  {m:<8} {p:<10} -> {len(d):>6} lines  ({os.path.basename(out)})")

    total = sum(sizes)
    assert total == len(rem), "round-robin lost lines"
    allk = set()
    for d in shards.values():
        allk |= set(d)
    assert len(allk) == len(rem), "shards overlap"
    print(f"disjoint + complete: OK  ({len(streams)} streams, {min(sizes)}-{max(sizes)} each)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
