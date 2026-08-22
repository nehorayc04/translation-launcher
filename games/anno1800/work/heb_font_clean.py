#!/usr/bin/env python3
"""heb_font_clean.py — build a SELF-CONTAINED Arabic-carrier font from the GAME's OWN Latin Meta
font, with ZERO bytes from the community Arabic mod (user choice 2026-07-30: "פונט עצמאי משלנו").

The Hebrew-as-Arabic disguise needs a Meta font that (a) carries the 27 carrier codepoints in its
cmap → Hebrew glyphs, (b) declares Arabic support so the engine's cold-boot Arabic bidi/shape
pipeline fires (OS/2 Arabic Unicode-range bit), and (c) provides the Arabic joining forms
(init/medi/fina) the pipeline expects — all pointing at the SAME Hebrew glyph so any position draws
Hebrew. The community mod's font supplied all this, but its Arabic glyph OUTLINES are its IP. Here we
REBUILD that exact structure programmatically on the game's own Latin base, so the output contains
only the game's Latin outlines + OUR Hebrew glyphs. Reference for what to build = the fan font's
tables (features aalt/ccmp/dlig/fina/init/liga/locl/medi/rlig/tnum, carrier→3 joining forms, OS/2
bit13), replicated — never copied byte-for-byte.

`build_clean_font(game_meta_bytes, hebrew_src_path)` -> (ttf_bytes, carrier_count).
"""
import io
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

# same 27 Hebrew letters -> 27 Arabic base carriers as heb_as_arabic (no alef/lam, no ligature)
_HEB = "אבגדהוזחטיךכלםמןנסעףפץצקרשת"
_ARB = [0x0628, 0x062A, 0x062B, 0x062C, 0x062D, 0x062E, 0x062F, 0x0630, 0x0631,
        0x0632, 0x0633, 0x0634, 0x0635, 0x0636, 0x0637, 0x0638, 0x0639, 0x063A,
        0x0641, 0x0642, 0x0643, 0x0645, 0x0646, 0x0647, 0x0648, 0x064A, 0x0629]
assert len(_HEB) == len(_ARB) == 27
_CONTROLS = (0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x061C)


def build_clean_font(game_meta_bytes: bytes, hebrew_src_path: str):
    tgt = TTFont(io.BytesIO(game_meta_bytes))          # the game's own Latin Meta font
    src = TTFont(hebrew_src_path)
    scale = tgt["head"].unitsPerEm / src["head"].unitsPerEm
    src_cmap = src.getBestCmap()
    src_gs = src.getGlyphSet()
    src_hmtx = src["hmtx"]
    glyf = tgt["glyf"]
    hmtx = tgt["hmtx"]
    orig_order = list(tgt.getGlyphOrder())              # a COPY of the game's original glyph order
    have = set(orig_order)
    added = []

    def _add(name, glyph, adv):
        if name in have:                                # avoid a name collision with the Latin base
            name = "z_" + name
        glyf.glyphs[name] = glyph                       # set the dict DIRECTLY (bypass __setitem__'s
        hmtx[name] = (adv, 0)                           #   own glyphOrder bookkeeping -> no double count)
        have.add(name)
        added.append(name)
        return name

    # render each Hebrew letter once (scaled to Meta upem) -> a NOMINAL glyph + 3 identical joining
    # forms (init/medi/fina). All four are the SAME Hebrew outline, so every Arabic position = Hebrew.
    empty = TTGlyphPen(glyphSet=None).glyph()
    nominal = {}          # carrier codepoint -> nominal glyph name
    forms = {}            # nominal name -> {init,medi,fina names}
    for heb_ch, carrier_cp in zip(_HEB, _ARB):
        hg = src_cmap.get(ord(heb_ch))
        if not hg:
            continue
        rec = DecomposingRecordingPen(src_gs)
        src_gs[hg].draw(rec)
        pen = TTGlyphPen(glyphSet=None)
        rec.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        g = pen.glyph()
        adv = int(round(src_hmtx[hg][0] * scale))
        nom = _add(f"heb{carrier_cp:04x}", g, adv)
        f_init = _add(f"heb{carrier_cp:04x}.init", pen.glyph(), adv)
        f_medi = _add(f"heb{carrier_cp:04x}.medi", pen.glyph(), adv)
        f_fina = _add(f"heb{carrier_cp:04x}.fina", pen.glyph(), adv)
        nominal[carrier_cp] = nom
        forms[nom] = (f_init, f_medi, f_fina)
    zwnj = _add("zwnj_empty", empty, 0)

    # real Hebrew block U+05D0-05EA -> the same nominal glyphs, so a field that renders live keyboard
    # input dynamically at least shows the typed letters (mirror-order; engine exe limitation).
    heb_block = {ord(hc): nominal[cp] for hc, cp in zip(_HEB, _ARB) if cp in nominal}

    full_order = orig_order + added
    tgt.setGlyphOrder(full_order)
    tgt["glyf"].glyphOrder = full_order

    # cmap: carriers -> nominal Hebrew, controls -> empty, real Hebrew block -> nominal, in every
    # Unicode subtable (the game font ships (0,3,4)+(3,1,4)).
    for st in tgt["cmap"].tables:
        if st.isUnicode():
            for cp, nom in nominal.items():
                st.cmap[cp] = nom
            for cp in _CONTROLS:
                st.cmap[cp] = zwnj
            for cp, nom in heb_block.items():
                st.cmap[cp] = nom

    # OS/2: declare Arabic support (bit 13 of ulUnicodeRange1) so the engine's Arabic pipeline fires.
    os2 = tgt["OS/2"]
    os2.ulUnicodeRange1 |= (1 << 13)

    # 🔴 match the fan font's PROVEN structure: drop the legacy (1,0) Mac cmap subtable. It lacks the
    # carriers, and if the engine consults it for lookup the carriers resolve to '?' (this is exactly
    # what made the first clean build render "?????"). The fan font kept only the Unicode (0,3)/(3,1)
    # subtables. Also match head.flags (fan 0x0003 vs the game base's 0x0019).
    tgt["cmap"].tables = [t for t in tgt["cmap"].tables if (t.platformID, t.platEncID) in ((0, 3), (3, 1))]
    tgt["head"].flags = 0x0003

    # GSUB: rebuild the Arabic joining features init/medi/fina, each carrier NOMINAL -> its positional
    # Hebrew copy (all Hebrew). This mirrors the fan font's proven structure without any fan bytes.
    if "GSUB" in tgt:
        del tgt["GSUB"]
    fea = ["languagesystem DFLT dflt;", "languagesystem arab dflt;"]
    for idx, feat in enumerate(("init", "medi", "fina")):
        fea.append(f"feature {feat} {{")
        for nom, (fi, fm, ff) in forms.items():
            fea.append(f"    sub {nom} by {(fi, fm, ff)[idx]};")
        fea.append(f"}} {feat};")
    addOpenTypeFeaturesFromString(tgt, "\n".join(fea))

    # sync the glyf table's own glyphOrder + maxp to the final font glyph order (setGlyphOrder /
    # feaLib don't reliably propagate to glyf.glyphOrder -> save asserts len(glyphOrder)==len(glyphs)).
    final = tgt.getGlyphOrder()
    tgt["glyf"].glyphOrder = final
    tgt["maxp"].numGlyphs = len(final)

    out = io.BytesIO()
    tgt.save(out)
    return out.getvalue(), len(nominal)


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from rda_reader import RDAArchive
    ORIG = r"F:/Game Lab/Anno 1800/maindata/data4.rda"
    HEB = r"C:/Windows/Fonts/frank.ttf"
    for fn in ("data/fonts/metaoffcpro-norm.ttf", "data/fonts/metaserifoffcpro-medium.ttf"):
        with RDAArchive(ORIG) as a:
            e = next(x for x in a.iter_entries() if x.name == fn)
            data = a.extract_entry(e)
        out, n = build_clean_font(data, HEB)
        f = TTFont(io.BytesIO(out))
        cm = f.getBestCmap()
        heb_ok = sum(1 for cp in _ARB if cp in cm)
        b13 = (f["OS/2"].ulUnicodeRange1 >> 13) & 1
        gsub = "GSUB" in f
        print(f"{fn}: {len(out):,} B  carriers={heb_ok}/27  OS2.arabic={b13}  GSUB={gsub}  glyphs={f['maxp'].numGlyphs}")
