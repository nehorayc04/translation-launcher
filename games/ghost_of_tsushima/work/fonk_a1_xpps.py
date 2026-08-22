#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_xpps.py — list all .xpps package names (grep ui/font/frontend/menu/hud),
and search accessible extracted data for the real FONTK/SFontData bytes."""
import os, re, sys

GAME = r"F:/Games/Ghost of Tsushima DC"
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "extract")
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R

UIPAT = re.compile(r"ui|font|frontend|front_end|menu|hud|glyph|text|type|kanji|char|title|shell|boot|common|core|global|misc|main", re.I)


def main():
    print("== all .xpps package names across misc archives (ui/font/frontend-ish flagged) ==")
    allx = []
    for f in sorted(os.listdir(PSARC_DIR)):
        if not (f.startswith("gapack_misc") and f.endswith(".psarc")): continue
        p = os.path.join(PSARC_DIR, f)
        try:
            arc = R.Psarc2(p); paths=[e.path for e in arc.files()]; arc.d.f.close()
        except Exception as ex:
            print(f"   {f}: ERR {ex}"); continue
        xpps = [x for x in paths if x.endswith(".xpps")]
        allx += [(f,x) for x in xpps]
    print(f"   total .xpps: {len(allx)}")
    # unique basenames
    base = {}
    for f,x in allx:
        b = x.rsplit("/",1)[-1]
        base.setdefault(b, f)
    # flag ui/font-ish
    flagged = sorted(b for b in base if UIPAT.search(b))
    print(f"\n   {len(flagged)} ui/font/frontend/menu-ish package names:")
    for b in flagged:
        print(f"      {base[b]:26s} {b}")
    # also: any name literally containing 'font'
    fnames = sorted(b for b in base if "font" in b.lower())
    print(f"\n   names containing 'font': {fnames or '(none)'}")
    # show a sample of ALL distinct basenames to eyeball
    print(f"\n   ALL {len(base)} distinct .xpps basenames:")
    for b in sorted(base):
        print(f"      {b}   [{base[b]}]")

    # search extracted files for FONTK / SFontData raw bytes
    print("\n== raw FONTK / SFontData search in extract/ ==")
    for fn in os.listdir(EX):
        p = os.path.join(EX, fn)
        if not os.path.isfile(p): continue
        d = open(p,"rb").read()
        for needle in (b"FONTK", b"SFontData", b"FontGlyphs", b"FontVerts"):
            c = d.count(needle)
            if c:
                i = d.find(needle)
                print(f"   {fn}: {needle!r} x{c} first@0x{i:x}")


if __name__ == "__main__":
    main()
