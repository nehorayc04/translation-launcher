#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_title.py — extract ghost_title.xpps (real title text glyphs) and analyze its
glyph table: real metrics (not a ramp?), the 24-byte geometry per real letter, and
locate the FontVerts buffer by looking at what surrounds the table + correlating."""
import os, sys, struct
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import got_fonk as GF
GREC = 64


def get_cached(archive, name, cf):
    cp = os.path.join(CACHE, cf)
    if os.path.exists(cp) and os.path.getsize(cp) > 0:
        return open(cp, "rb").read()
    arc = R.Psarc2(os.path.join(PD, archive))
    t = next((e for e in arc.files() if e.path.rstrip('/').endswith(name)), None)
    d = arc.extract(t)
    arc.d.f.close()
    open(cp, "wb").write(d)
    print(f"cached {name} ({len(d):,} B)")
    return d


def main():
    data = get_cached("gapack_misc_g.psarc", "ghost_title.xpps", "ghost_title.bin")
    print(f"ghost_title size={len(data):,} magic={data[:4]!r}")
    tbls = GF.find_rich_tables(data, min_run=6)
    print(f"RICH tables: {len(tbls)}")
    for s, cps, e in sorted(tbls, key=lambda t: -len(t[1]))[:20]:
        print(f"  @0x{s:x}..0x{e:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}]")

    # take the table covering ASCII letters; dump real letter records
    cand = [t for t in tbls if any(0x41 <= c <= 0x5a for c in t[1])]
    if not cand:
        print("no ASCII-letter table found")
        return
    s, cps, e = max(cand, key=lambda t: len(t[1]))
    print(f"\n== analyzing table @0x{s:x} n={len(cps)} ==")
    # metric ramp check + dump per-letter
    print(" cp    metric(+4)   +12u32    +14 +16u16 +20u16 | 24B-geom")
    recmap = {}
    q = s
    for c in cps:
        r = data[q:q + GREC]
        recmap[c] = r
        q += GREC
    prev_m = None
    ramp = True
    for c in cps:
        r = recmap[c]
        m = struct.unpack_from("<f", r, 4)[0]
        if prev_m is not None and abs((m - prev_m)) > 1e-6:
            pass
        prev_m = m
    for c in sorted(recmap):
        if not (0x20 <= c <= 0x7f):
            continue
        r = recmap[c]
        m = struct.unpack_from("<f", r, 4)[0]
        f12 = struct.unpack_from("<I", r, 12)[0]
        b14 = r[14]
        h16 = struct.unpack_from("<H", r, 16)[0]
        h20 = struct.unpack_from("<H", r, 20)[0]
        ch = chr(c)
        print(f"  {ch}  {m:10.4f}  0x{f12:08x} {b14:3d} 0x{h16:04x} 0x{h20:04x} | {r[22:46].hex()}")

    # decode the 24-byte geom of real letters as 6 f32
    print("\n== 24B geom as 6 f32 for O,L,I,i,l,M,W ==")
    for c in (0x4f, 0x4c, 0x49, 0x69, 0x6c, 0x4d, 0x57):
        if c in recmap:
            g = recmap[c][22:46]
            f = struct.unpack_from("<6f", g, 0)
            print(f"  '{chr(c)}': {[round(x,3) for x in f]}")

    # what's before/after the table
    def hd(b, base):
        return "\n".join(f"  {base+i:08x}  {b[i:i+16].hex()}  " +
                         "".join(chr(x) if 32 <= x < 127 else '.' for x in b[i:i+16])
                         for i in range(0, len(b), 16))
    print(f"\n== 96B BEFORE table @0x{s-96:x} ==")
    print(hd(data[s - 96:s], s - 96))
    print(f"\n== 160B AFTER table @0x{e:x} ==")
    print(hd(data[e:e + 160], e))


if __name__ == "__main__":
    main()
