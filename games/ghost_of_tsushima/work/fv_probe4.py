#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe4.py — focus on m_lm_menu GROUP-1 text glyphs (cp 0x27..0x4c, distinct
geometry). Decode the 24-byte block every way, find the field(s) that increase with
cp (candidate vertOffset/vertCount), and column-analyze ONLY the distinct-geometry glyphs."""
import os, sys, struct
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R
GREC = 64
PLACEHOLDER = bytes.fromhex("6a3cde46c4552dc9")  # first 8 of the shared placeholder


def get(a, n):
    arc = R.Psarc2(os.path.join(PD, a))
    t = next((e for e in arc.files() if e.path.rstrip('/').endswith(n)), None)
    d = arc.extract(t) if t else None
    arc.d.f.close()
    return d


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    # collect group-1 real glyphs: +14==1, geometry != placeholder
    recs = []
    q = 0x41abe
    while q + GREC <= 0x44000:
        if struct.unpack_from("<I", data, q + 8)[0] != 4:
            break
        cp = struct.unpack_from("<H", data, q)[0]
        r = data[q:q + GREC]
        recs.append((cp, r))
        q += GREC
    grp1 = [(cp, r) for cp, r in recs if r[14] == 1 and r[22:30] != PLACEHOLDER]
    print(f"group-1 real text glyphs (non-placeholder): {len(grp1)}")
    print(f"cps: {[hex(c) for c,_ in grp1]}")

    # decode the 24-byte block [+22..+45] every way for the first several
    print("\n== 24-byte block decoded as 6 f32 / 12 i16 / 6 u32 (cp order) ==")
    for cp, r in grp1[:16]:
        g = r[22:46]
        f = struct.unpack_from("<6f", g, 0)
        u = struct.unpack_from("<6I", g, 0)
        ch = chr(cp) if 32 <= cp < 127 else f"{cp:#x}"
        print(f"  {ch:>3}: f32={[round(x,2) for x in f]}")

    # find fields that increase monotonically with cp (candidate vertOffset)
    print("\n== monotonic-with-cp scan within the 24-byte block (u32 @ each byte pos) ==")
    for pos in range(0, 21):
        col = [struct.unpack_from("<I", r[22:46], pos)[0] for _, r in grp1]
        mono = all(col[i] <= col[i + 1] for i in range(len(col) - 1))
        # also as f32
        colf = [struct.unpack_from("<f", r[22:46], pos)[0] for _, r in grp1]
        monof = all(colf[i] <= colf[i + 1] for i in range(len(colf) - 1))
        if mono or monof:
            print(f"  +{pos}: u32-mono={mono} f32-mono={monof}  f32sample={[round(x,1) for x in colf[:6]]}..{[round(x,1) for x in colf[-3:]]}")

    # decode first f32 (the ~27000 field) precisely + deltas
    print("\n== first f32 of block (@+22) across group-1 + deltas ==")
    prev = None
    for cp, r in grp1:
        x = struct.unpack_from("<f", r, 22)[0]
        d = "" if prev is None else f"  d={x-prev:+.1f}"
        ch = chr(cp) if 32 <= cp < 127 else f"{cp:#x}"
        print(f"  {ch:>3} cp=0x{cp:x}: {x:.2f}{d}")
        prev = x

    # second f32 (@+26)
    print("\n== second f32 of block (@+26) ==")
    for cp, r in grp1[:12]:
        x = struct.unpack_from("<f", r, 26)[0]
        ch = chr(cp) if 32 <= cp < 127 else f"{cp:#x}"
        print(f"  {ch:>3}: {x:.4f}   (raw {r[26:30].hex()})")


if __name__ == "__main__":
    main()
