#!/usr/bin/env python3
"""heb_as_arabic.py — render Hebrew on Anno 1800's ENGLISH slot at COLD BOOT, no
language switch, by DISGUISING Hebrew as the Arabic script.

WHY: Anno's engine has a built-in Arabic text pipeline (bidi RTL + HarfBuzz shaping)
that IS pre-baked into the English-slot cold-boot atlas (PROVEN in-game 2026: a pure
DATA fan-mod — Arabic text in texts_english.xml + Arabic glyphs injected into the Meta
fonts — renders full Arabic RTL at cold boot on the retail Denuvo exe, no exe change).
The engine has NO such pipeline for the Hebrew block (U+05xx) — that gate is in the
protected exe and unreachable. So we ride the ARABIC pipeline:

  1. Map each Hebrew letter -> a distinct Arabic BASE letter (a "carrier").
  2. Store the Hebrew text with letters replaced by carriers (LOGICAL order — the engine
     bidi's it RTL for free), inserting ZWNJ (U+200C) between adjacent carriers so the
     shaper NEVER joins them or forms ligatures -> every carrier renders ISOLATED.
  3. Inject the HEBREW glyph at each carrier's isolated/base glyph in the Meta font.

Result: the engine sees "Arabic", runs bidi+shape, draws our Hebrew glyphs, RTL, at
cold boot, on English, with zero switch. Pure data; no exe touched.

Carriers exclude alef (U+0627) and lam (U+0644) to dodge the mandatory lam-alef ligature.
"""
import io
import re
import unicodedata

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

ZWNJ = "‌"

# 27 Hebrew letters (22 + 5 finals) -> 27 Arabic base carriers (no alef/lam).
_HEB = "אבגדהוזחטיךכלםמןנסעףפץצקרשת"
_ARB = [0x0628, 0x062A, 0x062B, 0x062C, 0x062D, 0x062E, 0x062F, 0x0630, 0x0631,
        0x0632, 0x0633, 0x0634, 0x0635, 0x0636, 0x0637, 0x0638, 0x0639, 0x063A,
        0x0641, 0x0642, 0x0643, 0x0645, 0x0646, 0x0647, 0x0648, 0x064A, 0x0629]
assert len(_HEB) == len(_ARB) == 27, (len(_HEB), len(_ARB))
CARRIER = {h: chr(a) for h, a in zip(_HEB, _ARB)}          # hebrew char -> arabic carrier char
CARRIER_CPS = set(_ARB)                                    # arabic carrier codepoints
_HEB_SET = set(_HEB)

_ARABIC_RANGE = lambda cp: 0x0600 <= cp <= 0x06FF          # noqa: E731


def remap_text(s: str) -> str:
    """Hebrew logical text -> carrier text: swap each Hebrew letter for its Arabic carrier
    and put ZWNJ between adjacent carriers so each renders isolated (no joining/ligatures).
    Everything else (Latin, digits, punctuation, <tags>, [tokens], %spec) is left verbatim —
    the engine's Arabic bidi lays those out as LTR islands, exactly like the fan Arabic mod."""
    out = []
    prev_carrier = False
    for ch in s:
        if ch in CARRIER:
            if prev_carrier:
                out.append(ZWNJ)          # isolate from the previous carrier
            out.append(CARRIER[ch])
            prev_carrier = True
        else:
            out.append(ch)
            prev_carrier = False
    return "".join(out)


def _isolated_cp(base_cp: int):
    """The Arabic-Presentation-Forms codepoint whose decomposition is '<isolated> base'."""
    for cp in range(0xFB50, 0xFEFF + 1):
        d = unicodedata.decomposition(chr(cp))
        if d.startswith("<isolated>") and d.split()[-1].lower() == f"{base_cp:04x}":
            return cp
    return None


def _single_subst_outputs(tgt: TTFont, base_gnames: set):
    """Walk GSUB and return {input_glyph_name -> set(output_glyph_names)} for EVERY
    single-substitution (LookupType 1, incl. extension type 7) whose INPUT is one of our
    carrier base glyphs. This catches the Arabic joining forms init/medi/fina/isol/locl/aalt —
    the shaped presentation glyphs that a joined carrier run actually draws with. Overwriting
    them too makes each carrier render Hebrew regardless of whether the shaper isolates or joins."""
    reach = {}
    if "GSUB" not in tgt:
        return reach
    gsub = tgt["GSUB"].table
    if not getattr(gsub, "LookupList", None):
        return reach
    for lk in gsub.LookupList.Lookup:
        for st in lk.SubTable:
            # unwrap extension (LookupType 7)
            m = getattr(st, "mapping", None)
            if m is None and hasattr(st, "ExtSubTable"):
                m = getattr(st.ExtSubTable, "mapping", None)
            if not m:
                continue
            for inp, out in m.items():
                if inp in base_gnames and isinstance(out, str):
                    reach.setdefault(inp, set()).add(out)
    return reach


def build_font(meta_font_bytes: bytes, hebrew_src_path: str) -> bytes:
    """Take the fan Arabic Meta font (proven to render via the engine's Arabic pipeline) and
    OVERWRITE, for each carrier, its base glyph AND every joining/presentation form (isolated,
    initial, medial, final, and any GSUB single-subst variant) with the mapped Hebrew letter's
    glyph (scaled to Meta's upem). Everything else in the font is left untouched. Overwriting
    ALL forms — not just base+isolated — is the fix for labels/paragraphs rendering joined Arabic:
    wherever the shaper picks a contextual form, it now draws Hebrew. Returns (TTF bytes, count)."""
    tgt = TTFont(io.BytesIO(meta_font_bytes))
    src = TTFont(hebrew_src_path)
    scale = tgt["head"].unitsPerEm / src["head"].unitsPerEm
    src_cmap = src.getBestCmap()
    src_gs = src.getGlyphSet()
    src_hmtx = src["hmtx"]
    tgt_cmap = tgt.getBestCmap()
    tgt_glyf = tgt["glyf"]
    tgt_hmtx = tgt["hmtx"]

    # 1. render each carrier's Hebrew glyph once, and map its base glyph name.
    heb_glyph = {}   # carrier base glyph name -> (glyph, advance)
    base_gnames = set()
    for heb_ch, carrier_ch in CARRIER.items():
        base_cp = ord(carrier_ch)
        heb_gname = src_cmap.get(ord(heb_ch))
        base_g = tgt_cmap.get(base_cp)
        if not heb_gname or not base_g:
            continue
        rec = DecomposingRecordingPen(src_gs)
        src_gs[heb_gname].draw(rec)
        pen = TTGlyphPen(glyphSet=None)
        rec.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        g = pen.glyph()
        adv = int(round(src_hmtx[heb_gname][0] * scale))
        heb_glyph[base_g] = (g, adv)
        base_gnames.add(base_g)

    # 2. collect ALL glyphs to overwrite per carrier: base + isolated (by cmap) + every
    #    GSUB single-subst output (init/medi/fina/isol/locl/aalt joining forms).
    targets = {bg: {bg} for bg in base_gnames}                     # base
    for heb_ch, carrier_ch in CARRIER.items():                     # isolated form by cmap
        base_cp = ord(carrier_ch)
        bg = tgt_cmap.get(base_cp)
        if not bg:
            continue
        iso = _isolated_cp(base_cp)
        if iso and iso in tgt_cmap:
            targets.setdefault(bg, {bg}).add(tgt_cmap[iso])
    for bg, outs in _single_subst_outputs(tgt, base_gnames).items():  # joining forms via GSUB
        targets.setdefault(bg, {bg}).update(outs)

    # 3. overwrite every collected glyph with its carrier's Hebrew glyph + advance.
    done = 0
    for bg, gnames in targets.items():
        g, adv = heb_glyph[bg]
        for gn in gnames:
            if gn in tgt_glyf:
                tgt_glyf[gn] = g
                tgt_hmtx[gn] = (adv, 0)
                done += 1

    # 4. CRITICAL: this Arabic donor font ships VISIBLE glyphs for the zero-width format chars,
    # so our ZWNJ separators drew a thin vertical bar between every letter. Empty them (0 contours,
    # 0 advance) -> truly invisible. Same fix as the RLM/LRM empty-glyph trick on other games.
    empty = TTGlyphPen(glyphSet=None).glyph()
    for cp in (0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x061C):
        g = tgt_cmap.get(cp)
        if g and g in tgt_glyf:
            tgt_glyf[g] = empty
            tgt_hmtx[g] = (0, 0)

    # 5. Map the REAL Hebrew block (U+05D0-05EA) to the (now-Hebrew) carrier glyphs, so a field
    # that renders live keyboard input dynamically (rename an island/ship/city) shows the letters
    # the user types instead of tofu. Pure cmap additions pointing at existing glyphs — no new
    # glyphs, safe on the static atlas (the pre-stored UI keeps using carriers). If the input field
    # is atlas-only it stays tofu, but this costs nothing and fixes it wherever input is dynamic.
    unicode_subtables = [st for st in tgt["cmap"].tables if st.isUnicode()]
    for heb_ch, carrier_ch in CARRIER.items():
        base_g = tgt_cmap.get(ord(carrier_ch))
        if base_g:
            for st in unicode_subtables:
                st.cmap[ord(heb_ch)] = base_g

    out = io.BytesIO()
    tgt.save(out)
    return out.getvalue(), done
