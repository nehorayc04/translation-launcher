#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_findfont.py — grep the EXE for the font-struct strings + surrounding
context (to find the real font resource name), and list small psarc TOCs for fonts."""
import os, re, sys

GAME = r"F:/Games/Ghost of Tsushima DC"
EXE  = os.path.join(GAME, "GhostOfTsushima.exe")
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))


def exe_strings():
    raw = open(EXE, "rb").read()
    print(f"== GhostOfTsushima.exe {len(raw):,} B ==")
    for needle in [b"SFontData", b"FontGlyphs", b"FontVerts", b"FONTK", b"FONT_KIND",
                   b"FONT_SIZE", b"Launcher_Font", b"fOnk", b"FontKind", b".fontk",
                   b"CreateFontW", b"AddFontMemResourceEx"]:
        s = 0; occ = []
        while True:
            i = raw.find(needle, s)
            if i < 0: break
            occ.append(i); s = i+1
        print(f"\n   {needle.decode():22s}: {len(occ)} occ")
        for o in occ[:3]:
            # surrounding ASCII strings (nul-delimited) window
            lo = raw.rfind(b"\x00", max(0,o-80), o)+1
            hi = raw.find(b"\x00", o)
            around = raw[max(0,o-64):o+80]
            near = [m.group().decode(errors="replace") for m in re.finditer(rb"[ -~]{4,}", around)]
            print(f"     @0x{o:x}: str={raw[lo:hi][:60]!r}  near={near}")


def list_small_psarcs():
    import dsar as R
    print("\n== small psarc TOCs — grep for font ==")
    small = []
    for f in sorted(os.listdir(PSARC_DIR)):
        if not f.endswith(".psarc"): continue
        p = os.path.join(PSARC_DIR, f)
        sz = os.path.getsize(p)
        if sz < 20_000_000:   # only small ones (fast)
            small.append((f, p, sz))
    print(f"   {len(small)} archives < 20MB: {[s[0] for s in small]}")
    fontpat = re.compile(r"font|glyph|fontk|typeface|\.fnt|charset", re.I)
    for f, p, sz in small:
        try:
            arc = R.Psarc2(p)
            paths = [e.path for e in arc.files()]
            arc.d.f.close()
        except Exception as ex:
            print(f"   {f}: ERR {ex}")
            continue
        fonts = [x for x in paths if fontpat.search(x)]
        # also show extension histogram
        exts = {}
        for x in paths:
            e = x.rsplit(".",1)[-1] if "." in x else x
            exts[e] = exts.get(e,0)+1
        top = sorted(exts.items(), key=lambda kv:-kv[1])[:6]
        print(f"   {f} ({sz//1024}KB, {len(paths)} files) top-ext={top}")
        for x in fonts[:12]:
            print(f"        FONT? {x}")


if __name__ == "__main__":
    exe_strings()
    list_small_psarcs()
