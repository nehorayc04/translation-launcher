#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_locate.py — extract candidate KCAP packages and search for the REAL font
tags FONTK / SFontData / FontGlyphs / FontVerts to pinpoint the in-game font."""
import os, sys

GAME = r"F:/Games/Ghost of Tsushima DC"
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R

CANDIDATES = [
    ("gapack_misc_c.psarc", "core_common.sprig.xpps"),
    ("gapack_misc_c.psarc", "core_tsu.sprig.xpps"),
    ("gapack_misc_c.psarc", "core_iki.sprig.xpps"),
    ("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps"),
    ("gapack_misc_d.psarc", "downloaded.sprig.xpps"),
    ("gapack_misc_g.psarc", "ghost_title.xpps"),
]
NEEDLES = [b"FONTK", b"SFontData", b"FontGlyphs", b"FontVerts", b"fOnk", b"KCAP"]


def get(archive, name):
    p = os.path.join(PSARC_DIR, archive)
    arc = R.Psarc2(p)
    tgt = None
    for e in arc.files():
        if e.path.rstrip("/").endswith(name):
            tgt = e; break
    if tgt is None:
        arc.d.f.close(); return None
    data = arc.extract(tgt)
    arc.d.f.close()
    return data


def main():
    for archive, name in CANDIDATES:
        try:
            data = get(archive, name)
        except Exception as ex:
            print(f"== {name} [{archive}]: EXTRACT ERR {ex}")
            continue
        if data is None:
            print(f"== {name} [{archive}]: not found in archive")
            continue
        print(f"== {name} [{archive}]: {len(data):,} B  magic={data[:8]!r}")
        for nd in NEEDLES:
            c = data.count(nd)
            if c:
                i = data.find(nd)
                print(f"     {nd!r}: x{c}  first@0x{i:x}  ctx={data[max(0,i-8):i+24].hex()}")
        # also: what resource-type strings does this package name-drop? (S-prefixed)
        import re
        stypes = set(m.group().decode() for m in re.finditer(rb"S[A-Z][A-Za-z]{4,20}", data))
        fonty = sorted(s for s in stypes if "Font" in s or "Glyph" in s or "Text" in s)
        if fonty:
            print(f"     S-types with Font/Glyph/Text: {fonty}")


if __name__ == "__main__":
    main()
