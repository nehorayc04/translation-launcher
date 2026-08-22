#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe5.py — decisive: (1) decode the icon glyphs' full 6-float geometry, (2) test
whether the '3 big floats with fixed exponent' are quantized offsets by extracting their
mantissa bits, (3) classify every sizable region of m_lm_menu (text / float-verts /
texture / records) to LOCATE FontVerts and decide atlas-vs-vector."""
import os, sys, struct, math
from collections import Counter
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R
GREC = 64


def get(a, n):
    arc = R.Psarc2(os.path.join(PD, a))
    t = next((e for e in arc.files() if e.path.rstrip('/').endswith(n)), None)
    d = arc.extract(t)
    arc.d.f.close()
    return d


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    # walk the whole glyph-record block
    recs = []
    q = 0x41abe
    while q + GREC <= 0x44000 and struct.unpack_from("<I", data, q + 8)[0] == 4:
        cp = struct.unpack_from("<H", data, q)[0]
        recs.append((cp, data[q:q + GREC]))
        q += GREC

    print("== icon glyphs cp 0x02..0x1e: full 6-float geom + +16 index ==")
    for cp, r in recs:
        if cp > 0x1e:
            break
        g = struct.unpack_from("<6f", r, 22)
        h16 = struct.unpack_from("<H", r, 16)[0]
        print(f"  cp=0x{cp:02x}: +16=0x{h16:04x}  f6={[round(x,2) for x in g]}")

    # extract mantissa of float0 and float1 across ALL records; is low-mantissa an index?
    print("\n== float0/float1 exponent stability + mantissa (checking quantization) ==")
    exp0 = Counter(); exp1 = Counter()
    for cp, r in recs:
        u0 = struct.unpack_from("<I", r, 22)[0]
        u1 = struct.unpack_from("<I", r, 26)[0]
        exp0[(u0 >> 23) & 0xff] += 1
        exp1[(u1 >> 23) & 0xff] += 1
    print(f"  float0 exponent histogram: {dict(exp0.most_common(6))}")
    print(f"  float1 exponent histogram: {dict(exp1.most_common(6))}")

    # classify the WHOLE package into regions: for each 256-byte window, entropy + float-density
    print("\n== region map of m_lm_menu (256B windows: class) ==")
    n = len(data)
    W = 256
    def classify(b):
        # text?
        printable = sum(1 for x in b if 32 <= x < 127 or x in (9, 10, 13))
        if printable / len(b) > 0.85:
            return "TEXT"
        # float-verts? density of plausible small floats
        fl = 0; tot = 0
        for p in range(0, len(b) - 3, 4):
            x = struct.unpack_from("<f", b, p)[0]
            tot += 1
            if x == 0 or (1e-3 < abs(x) < 4096 and x == x and not math.isinf(x)):
                fl += 1
        # entropy
        c = Counter(b); ent = -sum((v/len(b)) * math.log2(v/len(b)) for v in c.values())
        if ent > 7.5:
            return "HIENT(texture/comp)"
        if fl / tot > 0.85:
            return "FLOATS"
        if ent < 3.0:
            return "SPARSE"
        return f"mixed(e={ent:.1f})"
    # summarize contiguous same-class runs
    runs = []
    prev = None; start = 0
    for off in range(0, n - W, W):
        cls = classify(data[off:off + W])
        if cls != prev:
            if prev is not None:
                runs.append((start, off, prev))
            prev = cls; start = off
    runs.append((start, n, prev))
    # print only sizable runs
    for a, b, cls in runs:
        if b - a >= 1024:
            print(f"  0x{a:06x}..0x{b:06x}  {(b-a):>8,}  {cls}")


if __name__ == "__main__":
    main()
