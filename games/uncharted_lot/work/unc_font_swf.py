#!/usr/bin/env python3
r"""
unc_font_swf.py — add real Hebrew glyphs to a Scaleform DefineFont3 inside `fontlib-universal.swf`.

The in-game probe (proof #6) settled it: UNCHARTED's English UI is drawn by
`fontlib-universal.swf` **id7 = Albertus Medium** (rung 6 rendered the Euro; the vanish
control on `fontlib.swf id5` did NOT fire).  So Hebrew must be injected into THAT face.

Unlike a slot-hijack, 27 letters need 27 NEW code-table entries — and only ONE order-safe
gap exists (U+058F).  So this does a full DefineFont3 EXTEND via the proven Witcher 3 codec
(`swf_font.parse/serialize_definefont3`, byte-identical round-trip on all 7 fonts here):
parse → generate each Hebrew glyph shape from a TTF (`swf_glyphgen.glyph_to_shape`) →
insert (code, shape, advance, bounds) at the sorted position → serialize → splice the tag
back in, fixing the tag RECORDLENGTH and the SWF FileLength.

Why this is safe where `repoint` was not: `serialize_definefont3` RECOMPUTES every glyph
offset from scratch in glyph order, so the offset table is monotonic by construction — the
negative-length black-screen class ([[aliased-offset-black-screens]]) cannot occur.  Every
build is still run back through `unc_swf.validate()`.
"""
import os
import sys
import struct
import bisect

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "witcher3", "work"))
sys.path.insert(0, HERE)

import swf_font as SF                      # noqa: E402  parse/serialize DefineFont3
import swf_glyphgen as GG                  # noqa: E402  TTF outline -> SWF shape record
import unc_swf                             # noqa: E402
from fontTools.ttLib import TTFont         # noqa: E402
from fontTools.pens.boundsPen import BoundsPen  # noqa: E402

HEBREW = list(range(0x05D0, 0x05EB))       # 27 letters, contiguous
SWF_EM = 20480                             # Scaleform EM (id7 ascent=20429 ≈ this)
EMPTY_BOUNDS = b"\x08\x00"                 # id7's own per-glyph bounds RECT (nb=1, all 0)
DEF_FONT = os.path.join(ROOT, "games", "plague_tale_requiem", "work",
                        "font", "fonts_pdf", "DavidLibre-Bold.ttf")


def _hebrew_height(ttf, cmap, gs):
    bp = BoundsPen(gs)
    gs[cmap[0x05D0]].draw(bp)              # alef
    _, y0, _, y1 = bp.bounds
    return y1 - y0


def extend_font(swf_body, font_id, ttf_path=DEF_FONT, target_height=13000):
    """Return a NEW swf_body with the 27 Hebrew letters added to DefineFont3 `font_id`.

    target_height = the on-EM height of a Hebrew letter (≈0.63 EM reads a touch under the
    Latin caps, which suits Hebrew's lack of case — tune from a screenshot for the final).
    """
    # locate the tag
    hit = None
    for code, pos, ln in unc_swf.tags(swf_body):
        if code == 75 and struct.unpack_from("<H", swf_body, pos)[0] == font_id:
            hit = (pos, ln)
            break
    if hit is None:
        raise KeyError(f"no DefineFont3 id={font_id}")
    pos, ln = hit
    if ln < 0x3F:
        raise ValueError("short-form font tag; unexpected")

    f = SF.parse_definefont3(swf_body[pos:pos + ln])
    if not f["has_layout"]:
        raise ValueError("font has no layout table; advance/bounds cannot be extended safely")
    if not f["wide_codes"]:
        raise ValueError("narrow (u8) code table cannot hold Hebrew codepoints")

    ttf = TTFont(ttf_path)
    upm = ttf["head"].unitsPerEm
    cmap = ttf.getBestCmap()
    gs = ttf.getGlyphSet()
    hmtx = ttf["hmtx"]
    scale = target_height / _hebrew_height(ttf, cmap, gs)   # SWF units per TTF unit

    L = f["layout"]
    added = []
    for cp in HEBREW:
        if cp in f["codes"]:
            continue
        gname = cmap.get(cp)
        if gname is None:
            raise KeyError(f"TTF has no glyph for U+{cp:04X}")
        shape = GG.glyph_to_shape(gs, gname, scale, y_sign=-1)
        adv = round(hmtx[gname][0] * scale)
        j = bisect.bisect_left(f["codes"], cp)              # sorted insertion point
        f["codes"].insert(j, cp)
        f["shapes"].insert(j, shape)
        L["advance"].insert(j, adv)
        L["bounds"].insert(j, EMPTY_BOUNDS)
        f["num"] += 1
        added.append((cp, j, adv, len(shape)))

    new_tag = SF.serialize_definefont3(f)
    out = bytearray(swf_body)
    # 1. fix the tag RECORDLENGTH (long form: u32 at pos-4), then splice
    struct.pack_into("<I", out, pos - 4, len(new_tag))
    out[pos:pos + ln] = new_tag
    # 2. fix the SWF FileLength (u32 at bytes 4..8 = total uncompressed length)
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out), added, scale


def _cmd(args):
    import argparse
    from psarc import Psarc                                # noqa
    ap = argparse.ArgumentParser(description="verify Hebrew injection into a fontlib SWF")
    ap.add_argument("swf")
    ap.add_argument("--id", type=int, default=7)
    ap.add_argument("--ttf", default=DEF_FONT)
    a = ap.parse_args(args)
    body = open(a.swf, "rb").read()
    body, form = unc_swf.decompress(body)
    nb, added, scale = extend_font(body, a.id, a.ttf)
    print(f"scale={scale:.3f}  added {len(added)} glyphs")
    f = [x for x in unc_swf.fonts(nb) if x["id"] == a.id][0]
    heb = [c for c in f["codes"] if 0x05D0 <= c <= 0x05EA]
    print(f"id{a.id}: {f['n']} glyphs, {len(heb)}/27 Hebrew, sorted={f['codes']==sorted(f['codes'])}")
    probs = unc_swf.validate(nb)
    print("validate:", "clean" if not probs else probs)


if __name__ == "__main__":
    _cmd(sys.argv[1:])
