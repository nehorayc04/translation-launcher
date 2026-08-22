#!/usr/bin/env python3
"""
anno_font.py - inject Hebrew glyphs into Anno 1800 UI TrueType fonts.

Anno 1800's UI fonts (data/fonts/*.ttf inside data4.rda) are plain loose TTFs
covering Latin+Cyrillic only -- NO Hebrew (cmap-verified). Because they are loose
files, we don't need CR2W-embed (CP2077) or DDS-atlas (SM2/WD2/GoWR) injection:
we just ADD the Hebrew block (U+0590-05FF) into each Anno TTF, preserving the
font's own name/metrics/unitsPerEm so the engine loads "the same font" now with
Hebrew, and ship the result as a loose-file override at data/fonts/<name>.ttf.

Glyphs are copied from a source Hebrew TTF (default the classic Hebrew serif
Frank Ruehl = C:\\Windows\\Fonts\\frank.ttf, which matches Anno's Belle-Epoque
serifs; David is the clean alternative), scaled to the target unitsPerEm via a
TransformPen, given unique glyph names, and mapped in every Unicode cmap subtable.

CLI:
    anno_font.py inject  <target.ttf> <out.ttf> [hebrew_src.ttf]
    anno_font.py check   <font.ttf>            # report Hebrew/Latin/Cyrillic coverage
"""
import os
import sys

from fontTools.ttLib import TTFont, TTCollection
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Hebrew block we care about: letters U+05D0-05EA + final forms are inside it,
# plus the punctuation/points range. We copy whatever the source provides in
# U+0590-05FF (letters, niqqud, geresh/gershayim, maqaf) so every Hebrew string
# renders. We do NOT copy points we don't need, but copying the whole block is
# harmless and future-proofs niqqud.
HEB_LO, HEB_HI = 0x0590, 0x05FF

# CJK Latin-metric fix: a CJK UI font (e.g. Korean MD_CGothic) draws ASCII letters +
# digits as WIDE full/half-width CJK cells (0.5-0.63em) and renders at a larger px size
# than the Latin Meta font (Korean=36px vs Meta=32px), so "1920x1080"/"12 DirectX"/
# "V-Sync" look oversized and overflow/wrap. Fix: replace ONLY the ASCII outlines+advances
# (0x21-0x7E, NOT the 0x20 space) with MetaOffcPro's proportional ones, scaled so they
# render at Meta's on-screen size. CJK glyphs, the space, Hebrew, and vertical metrics are
# left untouched (touching the space/CJK corrupts the font -> "????").
LATIN_LO, LATIN_HI = 0x21, 0x7E
META_REF_PX = 32  # MetaOffcPro-Norm PHXFT render size (px); the look the user praised

DEFAULT_SRC_CANDIDATES = [
    r"C:\Windows\Fonts\narkisim.ttf",  # Narkisim - traditional Hebrew serif (user's pick; Belle-Epoque feel)
    r"C:\Windows\Fonts\frank.ttf",     # Frank Ruehl - classic Hebrew serif
    r"C:\Windows\Fonts\david.ttf",     # David - clean Hebrew
    r"C:\Windows\Fonts\arial.ttf",     # Arial - has Hebrew, universal fallback
]


def _pick_src(src):
    if src and os.path.exists(src):
        return src
    for c in DEFAULT_SRC_CANDIDATES:
        if os.path.exists(c):
            return c
    raise SystemExit("no Hebrew source font found (pass one explicitly)")


def _add_hebrew(tgt, src):
    """Add the Hebrew block from open TTFont `src` into open TTFont `tgt`
    (glyf+hmtx+cmap+glyphOrder), scaled to tgt's unitsPerEm. Returns (added, skipped).
    No-op if tgt has no glyf table (e.g. a CFF/.otf subfont) -> skipped all."""
    if "glyf" not in tgt:
        return 0, (HEB_HI - HEB_LO + 1)
    scale = tgt["head"].unitsPerEm / src["head"].unitsPerEm
    src_cmap = src.getBestCmap()
    src_gs = src.getGlyphSet()
    src_hmtx = src["hmtx"]
    tgt_glyf = tgt["glyf"]
    tgt_hmtx = tgt["hmtx"]
    tgt_cmaps = [t for t in tgt["cmap"].tables if t.isUnicode()]
    if not tgt_cmaps:
        return 0, 0
    added = skipped = 0
    for cp in range(HEB_LO, HEB_HI + 1):
        gname_src = src_cmap.get(cp)
        if not gname_src:
            continue
        new_name = "heb_%04X" % cp
        if new_name not in tgt_glyf:
            try:
                rec = DecomposingRecordingPen(src_gs)
                src_gs[gname_src].draw(rec)
                pen = TTGlyphPen(glyphSet=None)
                rec.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
                tgt_glyf[new_name] = pen.glyph()
            except Exception:
                skipped += 1
                continue
            tgt_hmtx[new_name] = (int(round(src_hmtx[gname_src][0] * scale)), 0)
            added += 1
        for t in tgt_cmaps:
            t.cmap[cp] = new_name
    order = tgt.getGlyphOrder()
    for cp in range(HEB_LO, HEB_HI + 1):
        nm = "heb_%04X" % cp
        if nm in tgt_glyf and nm not in order:
            order.append(nm)
    tgt.setGlyphOrder(order)
    # CRITICAL: the CJK fonts ship vertical-metrics tables (vhea/vmtx[/VORG]) sized
    # to the ORIGINAL glyph count. Adding glyphs without extending vmtx leaves it
    # short by 2 bytes/glyph -> the engine reads past EOF -> rejects the font ->
    # falls back to a no-Hebrew font -> "????" (fontTools hides this; it pads on
    # read). Anno's UI is horizontal-only (Meta has no vmtx and renders fine), so
    # strip the vertical tables entirely -> valid font, Hebrew renders.
    for vt in ("vmtx", "vhea", "VORG"):
        if vt in tgt:
            del tgt[vt]
    # CRITICAL: declare Hebrew support in OS/2. The font's glyf+cmap now HAVE Hebrew,
    # but OS/2 ulUnicodeRange/ulCodePageRange still say "no Hebrew". Anno's body/label/
    # popup widgets pre-rasterize a glyph atlas limited to the codepoint ranges the font
    # DECLARES in OS/2 -> with the Hebrew bits off, Hebrew is excluded from that atlas ->
    # "????" (while button/dropdown widgets render straight from cmap, so Hebrew worked
    # there). Setting ulUnicodeRange1 bit 11 (Hebrew block U+0590-05FF) + ulCodePageRange1
    # bit 5 (Windows-1255 Hebrew) makes the atlas include Hebrew.
    if "OS/2" in tgt:
        os2 = tgt["OS/2"]
        os2.ulUnicodeRange1 = os2.ulUnicodeRange1 | (1 << 11)
        if getattr(os2, "ulCodePageRange1", None) is not None:
            os2.ulCodePageRange1 = os2.ulCodePageRange1 | (1 << 5)
    # NOTE: do NOT narrow the U+0020 space here. ANY edit to the space metric/glyph of an
    # injected CJK font corrupts in-game rendering -> full "????" (confirmed twice). To get
    # a tighter word gap, switch the game to a CJK language whose font's NATIVE space is
    # narrower (Traditional Chinese dfpt_b5 = 0.33em vs Simplified dfhei5a = 0.50em).
    return added, skipped


def _substitute_latin(tgt, latin, scale):
    """Replace tgt's ASCII glyphs (0x21-0x7E, NOT the 0x20 space) with `latin`'s
    proportional outlines + advances, scaled by `scale`. Leaves the space, ALL CJK
    glyphs, Hebrew, and vertical metrics untouched. Returns count substituted.
    `scale` writes the latin (latin-upm) outline into tgt (tgt-upm) AND shrinks it so
    the CJK font's larger px render size matches Meta's: scale = (tgt_upm/latin_upm) *
    (META_REF_PX / tgt_render_px)."""
    if "glyf" not in tgt:
        return 0
    latin_cmap = latin.getBestCmap()
    latin_gs = latin.getGlyphSet()
    latin_hmtx = latin["hmtx"]
    tgt_glyf = tgt["glyf"]
    tgt_hmtx = tgt["hmtx"]
    tgt_cmap = tgt.getBestCmap()  # cp -> existing glyph name in target
    n = 0
    for cp in range(LATIN_LO, LATIN_HI + 1):
        lg = latin_cmap.get(cp)
        tg = tgt_cmap.get(cp)
        if not lg or not tg or tg not in tgt_glyf:
            continue
        try:
            rec = DecomposingRecordingPen(latin_gs)
            latin_gs[lg].draw(rec)
            pen = TTGlyphPen(glyphSet=None)
            rec.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
            tgt_glyf[tg] = pen.glyph()
        except Exception:
            continue
        aw, lsb = latin_hmtx[lg]
        tgt_hmtx[tg] = (int(round(aw * scale)), int(round(lsb * scale)))
        n += 1
    return n


def inject(target_path, out_path, hebrew_src=None, latin_src=None, latin_px=None):
    """Inject Hebrew into a .ttf OR a .ttc (TrueType Collection -> every subfont).
    If `latin_src`+`latin_px` are given, ALSO substitute proportional Latin/digit glyphs
    from latin_src (a Latin TTF path) scaled to render at META_REF_PX (the CJK Latin fix)."""
    src_path = _pick_src(hebrew_src)
    src = TTFont(src_path)
    latin = TTFont(latin_src) if latin_src else None
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    def _fix_latin(sub):
        if latin is None or not latin_px:
            return 0
        sc = (sub["head"].unitsPerEm / latin["head"].unitsPerEm) * (META_REF_PX / latin_px)
        return _substitute_latin(sub, latin, sc)

    if target_path.lower().endswith(".ttc"):
        coll = TTCollection(target_path)
        added = skipped = subbed = 0
        for sub in coll.fonts:
            a, s = _add_hebrew(sub, src)
            added += a
            skipped += s
            subbed += _fix_latin(sub)
        coll.save(out_path)
        return added, skipped, src_path, subbed
    tgt = TTFont(target_path)
    added, skipped = _add_hebrew(tgt, src)
    subbed = _fix_latin(tgt)
    tgt.save(out_path)
    return added, skipped, src_path, subbed


def check(path):
    f = TTCollection(path).fonts[0] if path.lower().endswith(".ttc") else TTFont(path)
    cm = f.getBestCmap()

    def has(a, b):
        return sum(1 for cp in range(a, b + 1) if cp in cm)
    print(f"{os.path.basename(path)}: glyphs~{len(cm)} "
          f"Hebrew={has(0x05D0,0x05EA)}/27 Latin={has(0x41,0x5A)}/26 "
          f"Cyrillic={'Y' if has(0x410,0x44F) else 'n'}")


def main(argv):
    if len(argv) >= 4 and argv[1] == "inject":
        src = argv[4] if len(argv) > 4 else None
        added, skipped, used, subbed = inject(argv[2], argv[3], src)
        print(f"injected {added} Hebrew glyphs (skipped {skipped}) from {used}; latin-subbed {subbed}")
        print(f"  -> {argv[3]}")
        check(argv[3])
        return 0
    if len(argv) >= 3 and argv[1] == "check":
        check(argv[2])
        return 0
    print("usage: anno_font.py inject <target.ttf> <out.ttf> [hebrew_src.ttf]\n"
          "       anno_font.py check <font.ttf>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
