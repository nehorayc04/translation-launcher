#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe6.py — full region map of m_lm_menu (ALL >=2KB regions, incl. after the glyph
tables), dump the largest non-glyph regions, and parse the KCAP trailer directory to
enumerate resources. Goal: definitively confirm whether a FontVerts buffer exists."""
import os, sys, struct, math
from collections import Counter
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R


def get(a, n):
    arc = R.Psarc2(os.path.join(PD, a))
    t = next((e for e in arc.files() if e.path.rstrip('/').endswith(n)), None)
    d = arc.extract(t)
    arc.d.f.close()
    return d


def classify(b):
    printable = sum(1 for x in b if 32 <= x < 127 or x in (9, 10, 13))
    if printable / len(b) > 0.85:
        return "TEXT"
    fl = tot = 0
    for p in range(0, len(b) - 3, 4):
        x = struct.unpack_from("<f", b, p)[0]
        tot += 1
        if x == 0 or (1e-3 < abs(x) < 4096 and x == x and not math.isinf(x)):
            fl += 1
    c = Counter(b); ent = -sum((v / len(b)) * math.log2(v / len(b)) for v in c.values())
    if ent > 7.4:
        return "HIENT"
    if tot and fl / tot > 0.85:
        return "FLOATS"
    if ent < 3.0:
        return "SPARSE"
    return f"mixed(e={ent:.1f})"


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    n = len(data)
    W = 512
    runs = []
    prev = None; start = 0
    for off in range(0, n - W, W):
        cls = classify(data[off:off + W])
        if cls != prev:
            if prev is not None:
                runs.append((start, off, prev))
            prev = cls; start = off
    runs.append((start, n, prev))
    print(f"m_lm_menu size={n:,} — regions >=2KB:")
    for a, b, cls in runs:
        if b - a >= 2048:
            print(f"  0x{a:06x}..0x{b:06x}  {(b-a):>8,}  {cls}")

    # biggest FLOATS region after glyph tables (>0x44000): dump as float pairs
    print("\n== largest FLOATS/HIENT regions after 0x44000 ==")
    big = [r for r in runs if r[0] >= 0x44000 and r[1] - r[0] >= 4096 and r[2] in ("FLOATS", "HIENT") or (r[2] == "FLOATS" and r[1]-r[0] >= 4096)]
    for a, b, cls in sorted(runs, key=lambda r: -(r[1] - r[0]))[:8]:
        if cls in ("FLOATS", "HIENT") or "mixed" in cls:
            print(f"  0x{a:x}..0x{b:x} {cls} ({b-a:,}B) sample floats: "
                  f"{[round(struct.unpack_from('<f', data, a + k*4)[0], 2) for k in range(8)]}")

    # KCAP trailer directory parse
    trailer = struct.unpack_from("<I", data, 0x2c)[0]
    print(f"\n== KCAP trailer @0x{trailer:x} (parse as 16B {{u64 a, u64 b}} records) ==")
    p = trailer
    idx = 0
    while p + 16 <= n and idx < 40:
        a, b = struct.unpack_from("<QQ", data, p)
        note = ""
        if b < n:
            note = f"  b->file? cls@b={classify(data[b:b+256]) if b+256<n else '?'}"
        if a == 0x454E4420 or b == 0x454E4420:
            note += "  <END>"
        print(f"  +0x{p-trailer:03x}: a=0x{a:016x} b=0x{b:016x}{note}")
        p += 16
        idx += 1


if __name__ == "__main__":
    main()
