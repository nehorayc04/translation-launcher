#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe7.py — test the 'float0 is a byte offset into a low-entropy vertex buffer'
hypothesis, and re-scan SPARSE regions as candidate outline buffers (outline coords are
mostly small/zero -> low entropy -> previously mis-tagged SPARSE)."""
import os, sys, struct
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


def hd(b, base):
    return "\n".join(f"  {base+i:08x}  {b[i:i+16].hex()}" for i in range(0, len(b), 16))


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    n = len(data)
    # gather all records
    recs = []
    q = 0x41abe
    while q + GREC <= 0x44000 and struct.unpack_from("<I", data, q + 8)[0] == 4:
        cp = struct.unpack_from("<H", data, q)[0]
        recs.append((cp, data[q:q + GREC]))
        q += GREC
    getrec = {cp: r for cp, r in recs}

    print("== test float0/float1/float2 as byte offsets for A,B,I,C,O and icons ==")
    for cp in (0x41, 0x42, 0x43, 0x49, 0x4f, 0x19, 0x1e, 0x02):
        if cp not in getrec:
            continue
        r = getrec[cp]
        f = struct.unpack_from("<3f", r, 22)
        ch = chr(cp) if 32 <= cp < 127 else f"{cp:#x}"
        offs = []
        for x in f:
            o = int(round(x))
            valid = 0 <= o < n
            offs.append((o, valid))
        print(f"  '{ch}' f0..2={[round(x,2) for x in f]} -> offsets {[(hex(o) if v else 'OOB') for o,v in offs]}")

    # dump the region float0 points at (~0x6800-0x7000) for a few glyphs
    print("\n== bytes at offset≈float0 for A,B,I ==")
    for cp in (0x41, 0x42, 0x49):
        o = int(round(struct.unpack_from("<f", getrec[cp], 22)[0]))
        if 0 <= o < n - 32:
            print(f"  '{chr(cp)}' @0x{o:x}:")
            print(hd(data[o - 4:o + 28], o - 4))

    # re-scan ALL regions treating 'outline' = high fraction of f32 in [-2,2] (glyph em space)
    print("\n== regions with high fraction of small floats in [-4,4] (candidate outline verts) ==")
    W = 256
    best = []
    for off in range(0, n - W, W):
        good = tot = 0
        for p in range(off, off + W - 3, 4):
            x = struct.unpack_from("<f", data, p)[0]
            tot += 1
            if x == 0.0 or (abs(x) < 4.0 and abs(x) > 1e-6 and x == x):
                good += 1
        frac = good / tot
        if frac >= 0.75:
            best.append((off, frac))
    # merge contiguous
    merged = []
    for off, frac in best:
        if merged and off == merged[-1][1]:
            merged[-1] = (merged[-1][0], off + W)
        else:
            merged.append((off, off + W))
    for a, b in merged:
        if b - a >= 512:
            sample = [round(struct.unpack_from('<f', data, a + k * 4)[0], 3) for k in range(10)]
            print(f"  0x{a:x}..0x{b:x} ({b-a}B) floats: {sample}")


if __name__ == "__main__":
    main()
