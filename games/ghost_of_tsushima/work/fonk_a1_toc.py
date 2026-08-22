#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_toc.py — read every psarc TOC (manifest only, cheap) and grep for a font
resource by name; then peek the .xpps magics in the small archives."""
import os, re, sys, struct

GAME = r"F:/Games/Ghost of Tsushima DC"
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R

FONTPAT = re.compile(r"font|glyph|fontk|typeface|\.fnt|charset|/ui|kanji_font|sdf", re.I)


def main():
    files = sorted(f for f in os.listdir(PSARC_DIR)
                   if f.endswith(".psarc") and not f.endswith(".he_backup"))
    print(f"== {len(files)} archives — TOC grep for font ==")
    allfont = []
    for f in files:
        p = os.path.join(PSARC_DIR, f)
        try:
            arc = R.Psarc2(p)
            paths = [e.path for e in arc.files()]
            arc.d.f.close()
        except Exception as ex:
            print(f"   {f}: ERR {ex}")
            continue
        fonts = [x for x in paths if FONTPAT.search(x)]
        # also collect distinct extensions
        exts = {}
        for x in paths:
            e = x.rsplit(".",1)[-1] if "." in x else "(none)"
            exts[e] = exts.get(e,0)+1
        interesting = {k:v for k,v in exts.items() if k not in ("sps",)}
        line = f"   {f:34s} {len(paths):6d} files  ext(non-sps)={interesting}"
        print(line)
        for x in fonts[:20]:
            print(f"        >>> {x}")
            allfont.append((f, x))
    print(f"\n== total font-name hits: {len(allfont)} ==")
    for f, x in allfont:
        print(f"   {f}: {x}")

    # peek xpps magics in a couple small archives (is any xpps NOT KCAP => font?)
    print("\n== xpps internal magics (KCAP=text; other=?) ==")
    for f in ["gapack_misc_a.psarc","gapack_misc_b.psarc","gapack_misc_d.psarc",
              "gapack_misc_e.psarc","gapack_misc_h.psarc","gapack_misc_k.psarc",
              "gapack_misc_n.psarc","gapack_misc_y.psarc"]:
        p = os.path.join(PSARC_DIR, f)
        try:
            arc = R.Psarc2(p)
            for e in arc.files():
                data = arc.extract(e)
                magic = data[:8]
                print(f"   {f}:{e.path}  size={len(data)}  magic={magic!r} ({magic[:4][::-1]!r})")
            arc.d.f.close()
        except Exception as ex:
            print(f"   {f}: ERR {ex}")


if __name__ == "__main__":
    main()
