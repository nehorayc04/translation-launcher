#!/usr/bin/env python3
"""
Patch the (loose) AvenirNextWorld-*.ttf fonts for the Arabic-slot Hebrew hijack:
point each Arabic CARRIER codepoint's cmap entry at the font's EXISTING Hebrew glyph.

The fonts already contain real Hebrew outlines (verified: contours=1, ink). We only add
cmap remaps -> no outline work. Because the Arabic GSUB shaping lookups key off the
original Arabic glyph ids (unchanged), and the carriers now resolve to Hebrew glyph ids,
shaping/ligatures never fire on them: the plain Hebrew glyph renders, RTL-ordered by the
engine's own bidi.

  python work/build_arabic_font_hijack.py            # -> work/refmods/he_fonts/*.ttf
  python work/build_arabic_font_hijack.py --deploy   # also copy into the game resources/
                                                       (backs up originals to resources/_he_backup/)
"""
import os
import sys
import glob
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from hebrew_arabic_hijack import HEB_TO_CARRIER

GAME = os.environ.get("ACBF_GAME", r"C:\Games\Assassin's Creed Black Flag Resynced")
RES = os.path.join(GAME, "resources")
OUTDIR = os.path.join(HERE, "refmods", "he_fonts")
BACKUP = os.path.join(RES, "_he_backup")


def patch_font(src, dst):
    from fontTools.ttLib import TTFont
    f = TTFont(src)
    best = f.getBestCmap()                       # codepoint -> glyphname
    # glyph name for each Hebrew codepoint (targets already in the font)
    heb_glyph = {}
    for h in HEB_TO_CARRIER:
        gn = best.get(h)
        if gn is None:
            raise RuntimeError(f"{os.path.basename(src)}: Hebrew U+{h:04X} missing from cmap")
        heb_glyph[h] = gn
    added = 0
    for table in f["cmap"].tables:
        if not table.isUnicode():
            continue
        for h, carrier in HEB_TO_CARRIER.items():
            table.cmap[carrier] = heb_glyph[h]   # carrier codepoint -> Hebrew glyph
            added += 1
    f.save(dst)
    f.close()
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUTDIR, exist_ok=True)
    fonts = sorted(glob.glob(os.path.join(RES, "AvenirNextWorld-*.ttf")))
    if not fonts:
        print(f"no AvenirNextWorld fonts in {RES}"); return 1
    print(f"patching {len(fonts)} fonts ({len(HEB_TO_CARRIER)} carrier remaps each)")
    for src in fonts:
        name = os.path.basename(src)
        dst = os.path.join(OUTDIR, name)
        n = patch_font(src, dst)
        print(f"  {name}: +{n} cmap remaps")
    if a.deploy:
        os.makedirs(BACKUP, exist_ok=True)
        for src in fonts:
            name = os.path.basename(src)
            bak = os.path.join(BACKUP, name)
            if not os.path.exists(bak):
                shutil.copyfile(src, bak)          # back up original once
            shutil.copyfile(os.path.join(OUTDIR, name), src)
        print(f"  DEPLOYED into {RES} (originals backed up in {BACKUP})")
    else:
        print(f"  built in {OUTDIR} (dry-run; use --deploy to install)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
