#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_extract.py — extract named .xpps resources from psarcs to a disk cache in the
scratchpad (so we scan them repeatedly without re-decompressing), then scan each for
RICH glyph tables and report what sits immediately after the biggest table."""
import os, sys, struct
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import got_fonk as GF

CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
os.makedirs(CACHE, exist_ok=True)

# (psarc, endswith-name, cache-filename)
TARGETS = [
    ("gapack_misc_c.psarc", "core_tsu.sprig.xpps", "core_tsu.bin"),
    ("gapack_misc_c.psarc", "core_iki.sprig.xpps", "core_iki.bin"),
    ("gapack_misc_g.psarc", "game.sprig.xpps", "game_sprig.bin"),
]


def extract_cached(archive, name, cachefile):
    cp = os.path.join(CACHE, cachefile)
    if os.path.exists(cp) and os.path.getsize(cp) > 0:
        return cp
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    if not tgt:
        arc.d.f.close()
        print(f"  {name}: NOT FOUND in {archive}")
        return None
    data = arc.extract(tgt)
    arc.d.f.close()
    with open(cp, "wb") as f:
        f.write(data)
    print(f"  cached {name} -> {cachefile} ({len(data):,} B)")
    return cp


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for archive, name, cachefile in TARGETS:
        if which != "all" and which not in cachefile:
            continue
        print(f"\n=== {name} ===")
        cp = extract_cached(archive, name, cachefile)
        if not cp:
            continue
        data = open(cp, "rb").read()
        print(f"  size={len(data):,}  magic={data[:4]!r}")
        tbls = GF.find_rich_tables(data, min_run=8)
        print(f"  RICH glyph tables: {len(tbls)}")
        for s, cps, e in sorted(tbls, key=lambda t: -len(t[1]))[:12]:
            arb = sum(1 for c in cps if 0x600 <= c <= 0x6ff)
            heb = sum(1 for c in cps if 0x590 <= c <= 0x5ff)
            cjk = sum(1 for c in cps if c >= 0x3000)
            tag = ""
            if arb: tag += f" ARABIC={arb}"
            if heb: tag += f" HEBREW={heb}"
            if cjk: tag += f" CJK={cjk}"
            print(f"    @0x{s:x}..0x{e:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}]{tag}")


if __name__ == "__main__":
    main()
