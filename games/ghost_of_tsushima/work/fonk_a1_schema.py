#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_schema.py — search texmeshman for the font schema strings, bound the
fOnk chunk via a coarse entropy map, and verify the rRxF 5488-byte period."""
import os, struct, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
TMM  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(TMM, "rb").read()
N = len(raw)


def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())


def findall(needle):
    out = []; s = 0
    while True:
        i = raw.find(needle, s)
        if i < 0: break
        out.append(i); s = i+1
    return out


def main():
    # 1) schema strings anywhere in the file
    print("== schema/field strings in texmeshman ==")
    for name in [b"SFontData", b"FontGlyphs", b"FontVerts", b"FONT_KIND",
                 b"FONT_SIZE", b"FONTK", b"fOnk", b"LARGE_FONT", b"Glyph",
                 b"glyph", b"Verts", b"Font", b"font", b"cmap", b"kern"]:
        occ = findall(name)
        tag = f"{len(occ)}"
        near = [f"0x{o:x}(fOnk{o-FONK_OFF:+d})" for o in occ if abs(o-FONK_OFF) < 3_000_000][:6]
        print(f"   {name.decode():12s}: {tag:>5} occ" + (f"  near-fOnk: {near}" if near else (f"  first: {[hex(o) for o in occ[:4]]}" if occ else "")))

    # 2) coarse entropy map ±3 MB around fOnk (64KB windows) to bound the chunk
    print("\n== coarse entropy map (64KB windows), fOnk-3MB .. fOnk+3MB ==")
    lo = max(0, FONK_OFF - 3_000_000)
    hi = min(N, FONK_OFF + 3_000_000)
    W = 65536
    prev_lo = None
    rows = []
    for p in range(lo, hi, W):
        h = ent(raw[p:p+W])
        rows.append((p, h))
    for p, h in rows:
        marker = "  <== fOnk" if p <= FONK_OFF < p+W else ""
        bar = "#" * int(h*4)
        print(f"   {p:9x} (fOnk{p-FONK_OFF:+9d}): {h:.3f} {bar}{marker}")

    # 3) verify rRxF period + inspect anchors
    print("\n== rRxF occurrences (period check) ==")
    occ = findall(b"rRxF")
    near = [o for o in occ if abs(o-FONK_OFF) < 200000]
    print(f"   total rRxF in file: {len(occ)}; near fOnk: {len(near)}")
    for i in range(1, len(near)):
        print(f"     0x{near[i]:x}  (+{near[i]-near[i-1]} from prev)  ctx {raw[near[i]-6:near[i]+10].hex()}")

    # 4) same for the b1 39 79 8e delimiter: spacing between consecutive hits
    print("\n== 'b139798e' delimiter spacing (first 30) ==")
    D = bytes.fromhex("b139798e")
    docc = findall(D)
    for i in range(1, min(31, len(docc))):
        print(f"   0x{docc[i]:x}  (+{docc[i]-docc[i-1]})")

    # 5) Look for the START of the chunk: is there a size/count just before 'fOnk'?
    print("\n== bytes before fOnk (0x40) as ints ==")
    pre = raw[FONK_OFF-0x40:FONK_OFF]
    print("   hex:", pre.hex())
    print("   u32 LE:", [hex(x) for x in struct.unpack_from("<16I", pre, 0)])


if __name__ == "__main__":
    main()
