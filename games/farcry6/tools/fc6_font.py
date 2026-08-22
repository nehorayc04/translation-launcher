"""
Far Cry 6 Hebrew font injection  (games/farcry6/tools)

FC6 ships per-script UI fonts inside common.dat (all glyf/TrueType, NO Hebrew):
  * Noto Kufi Arabic   -> renders the Arabic-locale menu text  (Ar 232, Heb 0)
  * TT Commons Ubisoft -> the Latin UI font                    (Lat 26,  Heb 0)
Hebrew stored in the Arabic slot therefore renders as '?' (missing glyph).

Fix: merge the 27 Hebrew letters (U+05D0-05EA) from Heebo into BOTH families (all
weights) via anno_font._add_hebrew (glyf merge -> keeps Arabic+Latin, adds Hebrew +
sets the OS/2 Hebrew coverage bit).  Whichever font the engine routes Hebrew to,
it now has the glyphs.  Re-deployed by fc6_deploy as scheme-0 stored.

  inject_all(fat) -> {entry_hash: injected_ttf_bytes}
"""
import os, io, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "anno1800", "work"))
from fontTools.ttLib import TTFont
from anno_font import _add_hebrew  # proven glyf Hebrew-merge (Anno/Mirage)

_REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
DONOR = os.path.join(_REPO, "games", "spiderman2", "extracted", "_heebo", "Heebo-Medium.ttf")
DONOR_BOLD = os.path.join(_REPO, "games", "spiderman2", "extracted", "_heebo", "Heebo-Bold.ttf")

# families whose Hebrew we inject (name-substring match, all weights)
TARGET_FAMILIES = ("noto kufi arabic", "tt commons")


def _fam(ft):
    try:
        return (ft["name"].getDebugName(1) or "").lower()
    except Exception:
        return ""


def inject_all(fat, verbose=True):
    """Return {hash: injected_bytes} for every glyf UI font in a target family."""
    donor = TTFont(DONOR)
    donor_b = TTFont(DONOR_BOLD) if os.path.exists(DONOR_BOLD) else donor
    out = {}
    for e in fat.entries:
        if not (8000 <= e.unc <= 6_000_000):
            continue
        try:
            d = fat.read_data(e)
        except Exception:
            continue
        if d[:4] not in (b"\x00\x01\x00\x00", b"true", b"ttcf"):   # glyf sfnt only
            continue
        try:
            ft = TTFont(io.BytesIO(d))
        except Exception:
            continue
        fam = _fam(ft)
        if not any(t in fam for t in TARGET_FAMILIES):
            continue
        if "glyf" not in ft:
            continue
        src = donor_b if "bold" in fam or "semibold" in fam or "black" in fam else donor
        added, skipped = _add_hebrew(ft, src)
        buf = io.BytesIO(); ft.save(buf); buf = buf.getvalue()
        out[e.hash] = buf
        if verbose:
            # verify coverage on the produced bytes
            v = TTFont(io.BytesIO(buf)); cm = v.getBestCmap()
            heb = sum(1 for c in range(0x5d0, 0x5eb) if c in cm)
            ar = sum(1 for c in range(0x600, 0x6ff) if c in cm)
            lat = sum(1 for c in range(0x41, 0x5b) if c in cm)
            print(f"  {e.hash:016x} '{_fam(ft)}' +Hebrew={added} -> Heb={heb}/27 Ar={ar} Lat={lat}/26 ({len(d)}->{len(buf)}B)")
    return out


# ---------------------------------------------------------------------------
# LTR-slot hijack: FC6 converts the Arabic-locale display text to CP1256 before
# rendering (Thai/Hebrew -> '?', Latin+Arabic survive).  So Hebrew codepoints can
# never reach the font.  Instead map Hebrew glyph SHAPES onto LATIN codepoints
# (which survive CP1256, and don't Arabic-shape), replace those glyphs in the Latin
# UI font, and write the text as reversed Latin codepoints (store VISUAL).
from fontTools.pens.recordingPen import DecomposingRecordingPen  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from fontTools.pens.transformPen import TransformPen  # noqa: E402

LATIN_FAMILIES = ("tt commons",)   # the font that renders Latin in the Arabic locale


def _remap(tgt, src, mapping):
    """Overwrite tgt's glyph for each latin_cp with src's Hebrew hebrew_cp outline
    (scaled to tgt upem). mapping = {latin_cp: hebrew_cp}. Returns count."""
    scale = tgt["head"].unitsPerEm / src["head"].unitsPerEm
    src_cmap = src.getBestCmap(); src_gs = src.getGlyphSet(); src_hmtx = src["hmtx"]
    tgt_cmap = tgt.getBestCmap(); tgt_glyf = tgt["glyf"]; tgt_hmtx = tgt["hmtx"]
    n = 0
    for lcp, hcp in mapping.items():
        sg = src_cmap.get(hcp); tg = tgt_cmap.get(lcp)
        if not sg or not tg or tg not in tgt_glyf:
            continue
        rec = DecomposingRecordingPen(src_gs); src_gs[sg].draw(rec)
        pen = TTGlyphPen(glyphSet=None); rec.replay(TransformPen(pen, (scale, 0, 0, scale, 0, 0)))
        tgt_glyf[tg] = pen.glyph()
        tgt_hmtx[tg] = (int(round(src_hmtx[sg][0] * scale)), 0)
        n += 1
    for vt in ("vmtx", "vhea", "VORG"):
        if vt in tgt:
            del tgt[vt]
    return n


def remap_latin(fat, mapping, families=LATIN_FAMILIES, verbose=True):
    """Return {hash: remapped_ttf_bytes} for the Latin UI fonts, Hebrew shapes on Latin cps."""
    donor = TTFont(DONOR); donor_b = TTFont(DONOR_BOLD) if os.path.exists(DONOR_BOLD) else donor
    out = {}
    for e in fat.entries:
        if not (8000 <= e.unc <= 6_000_000):
            continue
        try:
            d = fat.read_data(e)
        except Exception:
            continue
        if d[:4] not in (b"\x00\x01\x00\x00", b"true", b"ttcf"):
            continue
        try:
            ft = TTFont(io.BytesIO(d))
        except Exception:
            continue
        fam = _fam(ft)
        if not any(t in fam for t in families) or "glyf" not in ft:
            continue
        src = donor_b if any(w in fam for w in ("bold", "semibold", "black")) else donor
        n = _remap(ft, src, mapping)
        buf = io.BytesIO(); ft.save(buf); out[e.hash] = buf.getvalue()
        if verbose:
            print(f"  remap {e.hash:016x} '{fam}' {n} Latin glyphs -> Hebrew")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from fc6_fat import Fat
    fat = Fat(sys.argv[1] if len(sys.argv) > 1 else r"F:/Game Lab/Far Cry 6/data_final/pc/common.fat")
    res = inject_all(fat)
    print(f"injected {len(res)} fonts")
