#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_font.py — inject Hebrew glyph ENTRIES into BIG_ARABIC's Fonts_Z and repack
FONT/ENGLISH.DPC via our pure-Python repacker.

--marker mode: each of the 27 Hebrew letters (U+05D0-05EA) is given a COPY of an
existing glyph's Character (default 'A'), touching NO texture. If Hebrew then renders
as that glyph in-game, the whole inject+repack+material/UV path is proven, and only
the atlas glyph-drawing remains.
"""
from __future__ import annotations
import argparse, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dpc_repack import DpcRepack
from fonts_z import FontsZ, char_to_cid, cid_to_char

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BIG_ARABIC_ID = 0xAFBE3792DDA3B358
HEBREW = [chr(c) for c in range(0x05D0, 0x05EB)]  # א..ת  (27 letters)
BACKUP = ".he_backup"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpc", default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--marker", default="A", help="copy this existing glyph for every Hebrew letter")
    ap.add_argument("--repurpose", action="store_true",
                    help="change 27 Arabic entries' cid->Hebrew in place (constant size, no new entries) "
                         "pointing at the marker glyph — isolates whether in-place cid lookup works")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--out", help="write the rebuilt DPC here (default: alongside)")
    args = ap.parse_args()

    if args.revert:
        bak = args.dpc + BACKUP
        if os.path.exists(bak):
            shutil.copy2(bak, args.dpc)
            print("reverted", args.dpc, "from", bak)
        else:
            print("no backup:", bak)
        return

    D = DpcRepack(args.dpc)
    # find BIG_ARABIC FontMap object among the data-block objects
    fm = next((o for o in D.db_objs if o.oid == BIG_ARABIC_ID), None)
    assert fm is not None, "BIG_ARABIC FontMap not found"
    fz = FontsZ(fm.body)
    src = fz.by_char(args.marker)
    assert src is not None, f"marker glyph {args.marker!r} not in font"
    print(f"BIG_ARABIC: {len(fz.entries)} glyphs; marker '{args.marker}' "
          f"mat={src.mat} box=({src.x0:.0f},{src.y0:.0f})-({src.x1:.0f},{src.y1:.0f})")

    if args.repurpose:
        # change 27 Arabic entries' cid -> Hebrew IN PLACE, point them at the marker
        # glyph (copy src box/mat/metrics). Count stays 349 -> data block does NOT
        # grow -> isolates in-place cid lookup with zero other confounds.
        def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF
        ar = [e for e in fz.entries
              if (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid))]
        assert len(ar) >= 27, f"only {len(ar)} arabic entries"
        for e, ch in zip(ar, HEBREW):
            e.cid = char_to_cid(ch)
            e.mat = src.mat
            e.adv, e.x0, e.y0, e.x1, e.y1 = src.adv, src.x0, src.y0, src.x1, src.y1
            e.bx, e.by = src.bx, src.by
        print(f"repurposed 27 Arabic entries -> Hebrew (pointing at '{args.marker}'); count stays {len(fz.entries)}")
    else:
        existing = {e.char for e in fz.entries}
        added = 0
        for ch in HEBREW:
            if ch in existing:
                continue
            e = src.copy()
            e.cid = char_to_cid(ch)
            fz.entries.append(e)
            added += 1
        print(f"added {added} Hebrew entries (total now {len(fz.entries)})")

    fm.body = fz.build()
    fm.dirty = True
    rebuilt = D.build()
    print(f"rebuilt DPC: {len(rebuilt)} bytes (orig {len(D.data)}, delta {len(rebuilt)-len(D.data):+d})")

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ENGLISH_he.DPC")
    open(out, "wb").write(rebuilt)
    print("wrote", out)

    if args.deploy:
        bak = args.dpc + BACKUP
        if not os.path.exists(bak):
            shutil.copy2(args.dpc, bak)
            print("backed up ->", bak)
        shutil.copy2(out, args.dpc)
        print("DEPLOYED ->", args.dpc)
        print("Launch the game (Text language = العربية) and check if Hebrew now shows "
              f"the '{args.marker}' glyph instead of blank.")


if __name__ == "__main__":
    main()
