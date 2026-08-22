#!/usr/bin/env python3
"""
find_logo_tables.py — let the GAME tell you which textures are logos.

Instead of guessing names or scoring pixels, scan a master resource (`Universe`) for u64
values that are real texture resource ids and cluster the hits. Any per-language lookup
table shows up as a run of texture ids a few bytes apart, and printing the cluster names
gives the complete per-language mapping — including variants whose names are encrypted in
a patch forge, because the id is the same everywhere.

This is the tool that should have run before any pixel search: a name filter only finds
the convention you guessed, and a shape filter only finds the layout you assumed (a
one-line subtitle strip scores 1 band and is rejected by a 3-band logo signature).

    python find_logo_tables.py <inventory.tsv> [--res 2107] [--near 64]
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = r"F:/Game Lab/Assassin's Creed Mirage"


def load_inventory(path):
    m = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 5 and p[1].isdigit():
            m.setdefault(int(p[1]), (p[0], p[4]))
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inventory")
    ap.add_argument("--forge", default=os.path.join(GAME, "DataPC.forge"))
    ap.add_argument("--res", type=int, default=2107)
    ap.add_argument("--near", type=int, default=64)
    a = ap.parse_args()

    inv = load_inventory(a.inventory)
    print(f"inventory: {len(inv):,} texture ids")

    fg = Forge(a.forge)
    ents = {e.id: e for e in fg.entries}
    if a.res in ents:
        e = ents[a.res]
    else:                                   # not an id — treat as an index
        e = fg.entries[a.res]
    blob = fg.read(e)
    fg.f.close()
    cfds, _ = acs_cfd.decode_resource(blob, acs_cfd._oodle())
    data = cfds[-1][0]
    print(f"scanning resource {e.id} ({len(data):,} B decoded) for texture ids ...")

    ids = np.array(sorted(inv), dtype=np.uint64)
    buf = np.frombuffer(data, dtype=np.uint8)
    hits = []
    for off in range(8):                    # ids need not be 8-byte aligned
        n = (len(buf) - off) // 8
        if n <= 0:
            continue
        v = buf[off:off + n * 8].view(np.uint64)
        idx = np.flatnonzero(np.isin(v, ids))
        for i in idx:
            hits.append((off + int(i) * 8, int(v[i])))
    hits.sort()
    print(f"{len(hits):,} texture-id reference(s) found\n")

    clusters, cur = [], []
    for pos, rid in hits:
        if cur and pos - cur[-1][0] > a.near:
            clusters.append(cur)
            cur = []
        cur.append((pos, rid))
    if cur:
        clusters.append(cur)

    big = [c for c in clusters if len(c) >= 3]
    print(f"{len(clusters)} cluster(s), {len(big)} with >=3 entries — showing those:\n")
    for c in big:
        print(f"--- cluster at 0x{c[0][0]:x}  ({len(c)} ids, stride "
              f"{c[1][0]-c[0][0] if len(c) > 1 else '?'})")
        for pos, rid in c:
            forge, name = inv[rid]
            print(f"    +{pos - c[0][0]:<5} {rid:<16} {name}")
        print()


if __name__ == "__main__":
    main()
