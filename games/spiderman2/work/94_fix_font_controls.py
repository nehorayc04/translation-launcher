"""94_fix_font_controls.py — make the Heebo bidi-control glyphs INVISIBLE.

The real root of the trailing "symbol" (2026-06-07): Heebo ships a *visible*
4-contour marker glyph for RLM (U+200F) and LRM (U+200E) — zero advance width but
real contours, so cohtml draws a little mark wherever an `&rlm;` sits. (PDF
U+202C / RLE U+202B aren't in Heebo at all → those drew .notdef boxes.) The game's
own Arabic font keeps these as EMPTY zero-width glyphs, which is why Arabic — which
relies on a trailing `&rlm;` to pin the sentence-final period to the left (RTL)
end — never shows a mark.

We need the `&rlm;` (it fixes the end-period side under the LTR container base),
so we can't delete it; instead we make our font render it as nothing, exactly like
the Arabic font: strip the contours from U+200F / U+200E so they become empty,
zero-width, invisible. 71_build_heebo_font_mod embeds the TTF as-is, so editing the
source TTFs is all that's needed.

Run from work/.  Backs up each TTF to <name>.bak94 before writing.
"""
import os, sys, shutil, array
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphCoordinates

HEEBO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extracted", "_heebo")
FONTS = ["Heebo-Regular.ttf", "Heebo-Medium.ttf", "Heebo-Bold.ttf", "Heebo-Black.ttf"]
CONTROLS = [0x200F, 0x200E]   # RLM, LRM — the ones Heebo draws as a visible mark

# 🔑 2026-07-26 — the PC-settings pages (and the pre-launch native dialog) run with an
# LTR paragraph base: the vanilla cohtml code sets only `--languageNormalAlignment`
# (alignment) and `cohinline`, and NEVER sets `direction`/`dir` anywhere — and cohtml
# honours ONLY Unicode bidi CONTROL chars, so no CSS can fix it. The correct lever is
# therefore an EMBEDDING: wrap each line in RLE(U+202B) … PDF(U+202C) to force an RTL
# base, exactly like the VirtualDJ fix. Heebo has NO glyph for those (they drew .notdef
# boxes — which is why they were banned until now), so we ADD them here as empty,
# zero-width glyphs, the same treatment RLM/LRM already get.
ADD_CONTROLS = [0x202A, 0x202B, 0x202C, 0x202D, 0x202E]  # LRE, RLE, PDF, LRO, RLO


def empty_glyph():
    g = Glyph()
    g.numberOfContours = 0
    g.coordinates = GlyphCoordinates([])
    g.endPtsOfContours = []
    g.flags = array.array("B")
    g.xMin = g.yMin = g.xMax = g.yMax = 0
    return g


def main() -> int:
    for fn in FONTS:
        path = os.path.join(HEEBO, fn)
        if not os.path.exists(path):
            print(f"  SKIP (missing): {fn}")
            continue
        # never clobber a pristine backup with an already-patched font
        if not os.path.exists(path + ".bak94"):
            shutil.copyfile(path, path + ".bak94")
        t = TTFont(path)
        cmap = t.getBestCmap()
        glyf = t["glyf"]
        hmtx = t["hmtx"]
        fixed = []
        for cp in CONTROLS:
            gn = cmap.get(cp)
            if gn and gn in glyf.glyphs:
                glyf[gn] = empty_glyph()
                hmtx[gn] = (0, 0)
                fixed.append(f"U+{cp:04X}({gn})")

        # --- ADD the embedding controls as empty glyphs (see ADD_CONTROLS note) ---
        added = []
        for cp in ADD_CONTROLS:
            gn = cmap.get(cp)
            if gn is None:
                gn = f"uni{cp:04X}"
                if gn not in glyf.glyphs:
                    glyf[gn] = empty_glyph()
                    hmtx[gn] = (0, 0)
                    order = t.getGlyphOrder()
                    if gn not in order:
                        t.setGlyphOrder(list(order) + [gn])
                        t["glyf"].setGlyphOrder(t.getGlyphOrder())
                # map it in EVERY unicode cmap subtable, or some renderers miss it
                for sub in t["cmap"].tables:
                    if sub.isUnicode():
                        sub.cmap[cp] = gn
                added.append(f"U+{cp:04X}")
            else:
                # present but possibly drawn — force it empty too
                glyf[gn] = empty_glyph()
                hmtx[gn] = (0, 0)
                added.append(f"U+{cp:04X}(existing)")
        t.save(path)
        # verify
        t2 = TTFont(path)
        c2 = t2.getBestCmap()
        chk, bad = [], []
        for cp in CONTROLS + ADD_CONTROLS:
            gn = c2.get(cp)
            if not gn:
                bad.append(f"U+{cp:04X}:UNMAPPED")
                continue
            g = t2["glyf"][gn]
            w = t2["hmtx"][gn][0]
            chk.append(f"U+{cp:04X}:c={g.numberOfContours},w={w}")
            if g.numberOfContours != 0 or w != 0:
                bad.append(f"U+{cp:04X}:NOT-EMPTY(c={g.numberOfContours},w={w})")
        print(f"  {fn}: emptied {fixed} | added {added}")
        print(f"      verify: {' '.join(chk)}")
        if bad:
            raise SystemExit(f"[!] {fn}: control glyphs not invisible -> {bad}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
