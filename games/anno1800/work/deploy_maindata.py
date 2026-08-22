#!/usr/bin/env python3
"""deploy_maindata.py — the ROBUST Anno 1800 Hebrew deploy.

The loose-file font override only reaches SOME native atlas contexts (menu/values got
Hebrew, but setting labels + the epilepsy warning + profile sub-text stayed Arabic even
after a full all-forms font fix). The fan Arabic mod, by contrast, worked EVERYWHERE —
because its fonts live in a maindata .rda, not a loose file. So we replicate the fan's
exact mechanism:

  1. Rebuild the fan's data4.rda with Hebrew-INJECTED fonts (all Arabic joining forms ->
     Hebrew) and deploy it INTO Steam maindata (backing up the fan original).
  2. Move the fan's data99.rda (the Arabic texts_english.xml base) to a backup folder so
     it stops loading — the base then falls back to the game's own ENGLISH, and our loose
     mod's ModOp overrides that to Hebrew carriers (proven to work: GUID 7 = 'האנה גוד').

This covers BOTH possible root causes in ONE launch (font-not-reaching-labels AND any
text-override gap), and honours the user's 'back up the other loading content' request.
Reversible: restore the two backed-up files. The loose mod (Documents/.../mods/
zzz_hebrew_translation) stays as-is and supplies the Hebrew text.
"""
import argparse, os, shutil, sys, io
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rda_reader import RDAArchive
from rda_writer import write_rda_blocks
import heb_as_arabic as H
import anno_font
from fontTools.ttLib import TTFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STEAM = r"C:/Program Files (x86)/Steam/steamapps/common/Anno 1800/maindata"
BACKUP = r"C:/Users/Nehoray_Cohen/Documents/Anno 1800/_disabled_fan_arabic_backup"
FONT_NAMES = {"data/fonts/metaoffcpro-norm.ttf", "data/fonts/metaserifoffcpro-medium.ttf"}


def anno_running():
    try:
        out = os.popen('tasklist /FI "IMAGENAME eq Anno1800.exe" /NH 2>NUL').read()
        return "Anno1800.exe" in out
    except Exception:
        return False


def build_injected_data4(steam_data4, heb_src):
    """Read the (fan) data4.rda PRESERVING its block grouping, inject Hebrew into its 2 fonts,
    keep the rest verbatim. Returns (blocks, injected_count). Blocks are rewritten with
    write_rda_blocks so the archive matches Anno's exact multi-block layout (byte-identical
    structure minus the larger font content), which the engine loads natively."""
    injected = 0
    with RDAArchive(steam_data4) as a:
        blocks = a.read_blocks()
    new_blocks = []
    for blk in blocks:
        nb = []
        for name, data in blk:
            if name in FONT_NAMES:
                data, done = H.build_font(data, heb_src)
                injected += 1
                print(f"    injected {name}: {done} glyphs -> Hebrew ({len(data):,} B)")
            nb.append((name, data))
        new_blocks.append(nb)
    return new_blocks, injected


def verify_data4(path):
    with RDAArchive(path) as a:
        ents = list(a.iter_entries())
        names = {e.name for e in ents}
        assert FONT_NAMES <= names, f"fonts missing: {FONT_NAMES - names}"
        for e in ents:
            if e.name in FONT_NAMES:
                f = TTFont(io.BytesIO(a.extract_entry(e)))
                cmap = f.getBestCmap(); glyf = f["glyf"]
                # a carrier + its joining forms must all == the Hebrew base sig
                base = cmap[0x0628]; bg = glyf[base]
                bsig = (bg.numberOfContours, getattr(bg, "xMax", None))
                forms = {}
                for lk in f["GSUB"].table.LookupList.Lookup:
                    for st in lk.SubTable:
                        m = getattr(st, "mapping", None) or getattr(getattr(st, "ExtSubTable", None), "mapping", None)
                        if m and base in m:
                            forms[m[base]] = 1
                allheb = all((glyf[g].numberOfContours, getattr(glyf[g], "xMax", None)) == bsig for g in forms)
                zwnj = glyf[cmap[0x200C]].numberOfContours
                print(f"    verify {e.name}: base+forms Hebrew={allheb and bsig[0]==1}  ZWNJ contours={zwnj}")
                assert allheb and bsig[0] == 1 and zwnj == 0
    return len(ents)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true", help="restore the backed-up fan files")
    ap.add_argument("--steam", default=STEAM)
    args = ap.parse_args()
    steam = args.steam
    d4 = os.path.join(steam, "data4.rda")
    d99 = os.path.join(steam, "data99.rda")
    os.makedirs(BACKUP, exist_ok=True)

    if args.revert:
        for fn in ("data4.rda", "data99.rda"):
            b = os.path.join(BACKUP, "fan_" + fn)
            if os.path.exists(b):
                shutil.copy2(b, os.path.join(steam, fn))
                print(f"restored {fn} from backup")
        print("reverted. (loose mod still active; the ORIGINAL base data4 with all fonts is not restored — "
              "only the fan's font/text rda are put back.)")
        return

    if anno_running():
        print("!! Anno1800.exe is RUNNING — close the game first (it locks maindata). Aborting.")
        return

    # 1. back up the fan originals (once)
    if os.path.exists(d4):
        b = os.path.join(BACKUP, "fan_data4.rda")
        if not os.path.exists(b):
            shutil.copy2(d4, b); print(f"backed up fan data4.rda -> {b} ({os.path.getsize(b):,} B)")
    if os.path.exists(d99):
        b = os.path.join(BACKUP, "fan_data99.rda")
        if not os.path.exists(b):
            shutil.copy2(d99, b); print(f"backed up fan data99.rda -> {b} ({os.path.getsize(b):,} B)")

    # 2. rebuild data4 with injected fonts (preserving the fan's exact multi-block layout),
    #    verify in a temp, then swap in. data99 (the Arabic text base) is LEFT IN PLACE — the
    #    loose mod's ModOp overrides it to Hebrew carriers (proven), and removing it blanks text.
    heb_src = anno_font._pick_src(None)
    print(f"  Hebrew source font: {heb_src}")
    blocks, injected = build_injected_data4(d4, heb_src)
    assert injected == 2, f"expected to inject 2 fonts, did {injected}"
    tmp = d4 + ".new"
    sz = write_rda_blocks(blocks, tmp)
    n = verify_data4(tmp)
    print(f"  built injected data4.rda: {sz:,} B, {n} entries — OK")
    os.replace(tmp, d4)
    print(f"  deployed -> {d4}  (data99 Arabic base kept; loose ModOp overrides it to Hebrew)")

    print("\nDONE. Steam maindata data4.rda now carries the Hebrew-injected fonts (used by the "
          "cold-boot pre-baked atlas that the loose fonts couldn't reach).")
    print("The loose mod (Documents/Anno 1800/mods/zzz_hebrew_translation) supplies the Hebrew text.")
    print("Launch cold (Text Language = English). To revert: python deploy_maindata.py --revert")


if __name__ == "__main__":
    main()
