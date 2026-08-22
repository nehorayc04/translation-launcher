#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_struct.py — map ghost_title.xpps structure: KCAP header/sections, ASCII tags
(SFontData/FontGlyphs/FontVerts/etc.), the region layout, and where the glyph-record
(+14,+16,+18) references could point. Read-only on the cached bin."""
import os, sys, struct, re, collections
import numpy as np

CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
GT = os.path.join(CACHE, "ghost_title.bin")
GREC = 64


def load():
    return open(GT, "rb").read()


def u16(d, p): return struct.unpack_from("<H", d, p)[0]
def u32(d, p): return struct.unpack_from("<I", d, p)[0]
def u64(d, p): return struct.unpack_from("<Q", d, p)[0]
def f32(d, p): return struct.unpack_from("<f", d, p)[0]


def hexdump(d, base, n=64):
    out = []
    for i in range(0, n, 16):
        chunk = d[base + i:base + i + 16]
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        out.append(f"  {base+i:08x}  {chunk.hex(' ')}  {asc}")
    return "\n".join(out)


def main():
    d = load()
    n = len(d)
    print(f"ghost_title.bin {n:,}B ({n:#x})  magic={d[:4]!r}")
    print("\n== first 128 bytes (KCAP header) ==")
    print(hexdump(d, 0, 128))

    # ---- find ASCII tags that look like section/type names
    print("\n== ASCII tokens (font-relevant) in the file ==")
    pats = [b"SFontData", b"FontGlyphs", b"FontVerts", b"FontData", b"Glyph", b"Verts",
            b"Font", b"KCAP", b"PACK", b"sprig", b"SFont", b"Kerning", b"Ligature"]
    for pat in pats:
        offs = []
        start = 0
        while True:
            i = d.find(pat, start)
            if i == -1:
                break
            offs.append(i)
            start = i + 1
            if len(offs) > 30:
                break
        if offs:
            print(f"  {pat.decode():12} x{len(offs):<4} first@ {[hex(o) for o in offs[:8]]}")

    # ---- Generic 4-byte ASCII tag scan around the header/section table
    print("\n== 4-char ASCII tags in first 4 KB (likely section directory) ==")
    for p in range(0, 4096, 4):
        tag = d[p:p + 4]
        if all(32 <= c < 127 for c in tag) and any(65 <= c < 91 or 97 <= c < 123 for c in tag):
            print(f"  @0x{p:x}: {tag!r}  next u32s: {u32(d,p+4)} {u32(d,p+8)} {u32(d,p+12)}")

    # ---- glyph tables span
    print("\n== glyph-record region (from fv_analyze: ~0x866952..~0x8aec92) ==")
    print("  what's right BEFORE 0x866952 (192 B):")
    print(hexdump(d, 0x866952 - 192, 192))

    # ---- max real +16 across all glyph records
    #      re-walk all tables quickly
    b = np.frombuffer(d, dtype=np.uint8)
    cand = np.nonzero((b[2:n - 1] == 0) & (b[3:n] == 0))[0]
    max16 = 0
    ref16 = []
    ref14 = []
    for pp in cand:
        p = int(pp)
        if p + GREC > n:
            continue
        if u16(d, p + 62) != 0xffff or u16(d, p + 20) != 0xf8:
            continue
        cp = u16(d, p)
        if not (1 <= cp <= 0xfffe):
            continue
        v16 = u16(d, p + 16)
        v14 = u16(d, p + 14)
        if v16 != 0xffff:
            ref16.append(v16)
            if v16 > max16:
                max16 = v16
        ref14.append(v14)
    print(f"\n== reference-field global stats (records with +20==0xf8 & +62==0xffff) ==")
    print(f"  count={len(ref14)}  max real +16={max16}  (0xffff excluded)")
    print(f"  +16 percentiles: {np.percentile(ref16,[0,50,90,99,100]).astype(int).tolist()}")
    print(f"  +14 max={max(ref14)} distinct={len(set(ref14))}")

    # ---- look for a fixed-stride descriptor table sized ~max16 entries.
    #      If (+16) indexes a table of stride S, the table has ~max16 entries.
    #      Search for repeating structured regions before the glyph tables.
    print("\n== scanning 0x0..0x866952 for candidate structured/dense float regions ==")
    W = 4096
    prev_kind = None
    seg_start = 0
    def kind_of(off):
        good = tot = 0
        zeros = 0
        for p in range(off, min(off + W, 0x866952) - 3, 4):
            x = struct.unpack_from("<f", d, p)[0]
            tot += 1
            if x == 0.0:
                zeros += 1
            elif abs(x) < 4000.0 and abs(x) > 1e-6 and x == x:
                good += 1
        if tot == 0:
            return "?"
        fz = zeros / tot
        fg = good / tot
        if fz > 0.9:
            return "ZERO"
        if fg > 0.6:
            return "FLOAT"
        return "OTHER"
    segs = []
    off = 0
    while off < 0x866952:
        k = kind_of(off)
        if not segs or segs[-1][2] != k:
            segs.append([off, off + W, k])
        else:
            segs[-1][1] = off + W
        off += W
    # print segments >= 32KB
    for a, bb, k in segs:
        if bb - a >= 32768:
            print(f"  0x{a:x}..0x{bb:x} ({(bb-a)//1024}KB) {k}")


if __name__ == "__main__":
    main()
