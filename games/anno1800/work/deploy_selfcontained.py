#!/usr/bin/env python3
"""deploy_selfcontained.py — LOCAL TEST of the CLEAN self-contained Arabic-carrier font.

Builds the self-contained Meta fonts (the GAME's own Latin base + OUR Hebrew glyphs + a rebuilt
Arabic joining structure -> ZERO bytes from the community Arabic mod) and deploys them into BOTH:
  * the loose mod  (Documents/.../mods/zzz_hebrew_translation/data/fonts/)  -> dynamic-render text
  * the Steam maindata data4.rda                                            -> cold-boot pre-baked labels

Backs up the current WORKING build first (revert with --revert). The loose mod's texts_english.xml
(already deployed by build_arabic_disguise) is untouched — this only swaps the fonts.

  python deploy_selfcontained.py            # deploy the self-contained fonts for the in-game test
  python deploy_selfcontained.py --revert   # restore the previous (fan-based) working build
"""
import argparse, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from rda_reader import RDAArchive
from rda_writer import write_rda_blocks
from heb_font_clean import build_clean_font

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STEAM   = r"C:/Program Files (x86)/Steam/steamapps/common/Anno 1800/maindata"
ORIG_D4 = r"F:/Game Lab/Anno 1800/maindata/data4.rda"   # game ORIGINAL (45MB) = clean Latin Meta fonts
HEB_SRC = r"C:/Windows/Fonts/frank.ttf"                  # test source; distribution bundles an OFL Hebrew font
LOOSE   = r"C:/Users/Nehoray_Cohen/Documents/Anno 1800/mods/zzz_hebrew_translation/data/fonts"
BACKUP  = r"C:/Users/Nehoray_Cohen/Documents/Anno 1800/_selfcontained_test_backup"
FONTS   = ["data/fonts/metaoffcpro-norm.ttf", "data/fonts/metaserifoffcpro-medium.ttf"]


def anno_running():
    try:
        return "Anno1800.exe" in os.popen('tasklist /FI "IMAGENAME eq Anno1800.exe" /NH 2>NUL').read()
    except Exception:
        return False


def build_fonts():
    out = {}
    for fn in FONTS:
        with RDAArchive(ORIG_D4) as a:
            e = next(x for x in a.iter_entries() if x.name == fn)
            data = a.extract_entry(e)
        ttf, n = build_clean_font(data, HEB_SRC)
        out[fn] = ttf
        print(f"  built {fn}: {len(ttf):,} B ({n}/27 carriers)")
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    d4 = os.path.join(STEAM, "data4.rda")
    os.makedirs(BACKUP, exist_ok=True)

    if args.revert:
        b = os.path.join(BACKUP, "prev_data4.rda")
        if os.path.exists(b):
            shutil.copy2(b, d4); print("restored Steam data4.rda from backup")
        for fn in FONTS:
            bf = os.path.join(BACKUP, os.path.basename(fn))
            if os.path.exists(bf):
                shutil.copy2(bf, os.path.join(LOOSE, os.path.basename(fn)))
        print("reverted loose fonts + Steam data4 to the previous (fan-based) working build.")
        return

    if anno_running():
        print("!! Anno1800.exe is RUNNING — close the game first (it locks maindata). Aborting.")
        return

    fonts = build_fonts()
    # back up the current WORKING build once (Steam data4 + loose fonts)
    if not os.path.exists(os.path.join(BACKUP, "prev_data4.rda")):
        shutil.copy2(d4, os.path.join(BACKUP, "prev_data4.rda"))
        print(f"  backed up current Steam data4.rda -> {BACKUP}\\prev_data4.rda")
    for fn in FONTS:
        lf = os.path.join(LOOSE, os.path.basename(fn)); bf = os.path.join(BACKUP, os.path.basename(fn))
        if os.path.exists(lf) and not os.path.exists(bf):
            shutil.copy2(lf, bf)

    # 1. loose mod fonts -> self-contained
    for fn in FONTS:
        open(os.path.join(LOOSE, os.path.basename(fn)), "wb").write(fonts[fn])
    print("  loose mod fonts -> self-contained")

    # 2. Steam maindata data4.rda: replace the 2 font entries, keep the blacklist block verbatim
    with RDAArchive(d4) as a:
        blocks = a.read_blocks()
    newb, replaced = [], 0
    for blk in blocks:
        nb = []
        for name, data in blk:
            if name in fonts:
                data = fonts[name]; replaced += 1
            nb.append((name, data))
        newb.append(nb)
    assert replaced == 2, f"expected to replace 2 fonts, replaced {replaced}"
    tmp = d4 + ".new"; sz = write_rda_blocks(newb, tmp); os.replace(tmp, d4)
    print(f"  Steam maindata data4.rda -> self-contained ({sz:,} B, {replaced} fonts)")

    # 3. verify: read the deployed fonts back, confirm they are the CLEAN self-contained build
    from fontTools.ttLib import TTFont
    import io as _io
    with RDAArchive(d4) as a:
        for fn in FONTS:
            e = next(x for x in a.iter_entries() if x.name == fn)
            f = TTFont(_io.BytesIO(a.extract_entry(e)))
            cm = f.getBestCmap()
            heb = sum(1 for cp in (0x0628, 0x062A, 0x0631, 0x0648) if cp in cm)
            print(f"    verify {fn}: glyphs={f['maxp'].numGlyphs} carriers~={heb}/4 "
                  f"OS2.arabic={(f['OS/2'].ulUnicodeRange1>>13)&1} GSUB={'GSUB' in f}")
    print("\nDONE. Launch the game COLD (Text Language = English). "
          "Revert: python deploy_selfcontained.py --revert")


if __name__ == "__main__":
    main()
