#!/usr/bin/env python3
"""
cc_font.py - inject Hebrew glyphs into Corsair Cove's UI fonts.

The game's real UI faces are cooked as LOOSE `.ufont` bulk files inside the
legacy pak `pakchunk0_s25-WinGDK.pak` (see cc_ufont.py for the container), so
this is the EASIEST font class in the project: unwrap -> glyf-merge the Hebrew
block -> re-wrap -> ship as a `_P.pak` loose-file override. No IoStore repack,
no atlas, no SDF.

Shipped faces (cmap-verified 0/27 Hebrew on every one):
    Alegreya-Regular / -SemiBold                 serif display  (glyf)
    AlegreyaSans-Regular/-Bold-FixedNumbers      sans UI        (glyf)
    Noto{Sans,Serif}{JP,KR,SC,TC}                CJK fallbacks  (JP=glyf, rest=CFF)

We inject into the FOUR Alegreya faces only: they are the game's own Latin UI
faces, so an unknown codepoint resolves there first. The CJK Notos are
per-culture fallbacks for ja/ko/zh (irrelevant to a Hebrew build) and most are
CFF/OTTO, where a glyf merge is a silent no-op anyway.

Donors (both SIL OFL, so redistributable):
    Alegreya  (calligraphic humanist serif) <- Frank Ruhl Libre  (Hebrew serif)
    Alegreya Sans (humanist sans)           <- Heebo             (Hebrew sans)

CLI:
    cc_font.py check  <dir-of-ufonts>
    cc_font.py inject <in-ufont-dir> <out-ufont-dir>
"""
import io
import os
import sys

from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "games", "anno1800", "work"))
sys.path.insert(0, HERE)

import anno_font  # noqa: E402  (reuses the proven glyf-merge helper)
import cc_ufont  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEB_LETTERS = range(0x05D0, 0x05EB)

# Donors are VENDORED next to this file so a build is self-contained and
# reproducible on any machine (both families are SIL OFL, so redistributable).
DONOR_DIR = os.path.join(HERE, "donors")
SERIF_DONOR = os.path.join(DONOR_DIR, "FrankRuhlLibre-Regular.ttf")
SERIF_DONOR_BOLD = os.path.join(DONOR_DIR, "FrankRuhlLibre-Medium.ttf")
SANS_DONOR = os.path.join(DONOR_DIR, "Assistant-Regular.ttf")
SANS_DONOR_BOLD = os.path.join(DONOR_DIR, "Assistant-Bold.ttf")

# target basename (lowercased) -> donor path
DONORS = {
    "alegreya-regular.ufont": SERIF_DONOR,
    "alegreya-semibold.ufont": SERIF_DONOR_BOLD,
    "alegreyasans-regular-fixednumbers.ufont": SANS_DONOR,
    "alegreyasans-bold-fixednumbers.ufont": SANS_DONOR_BOLD,
}


def hebrew_coverage(sfnt_bytes):
    f = TTFont(io.BytesIO(sfnt_bytes), lazy=True)
    cm = set()
    for t in f["cmap"].tables:
        cm |= set(t.cmap.keys())
    n = sum(1 for c in HEB_LETTERS if c in cm)
    latin = sum(1 for c in range(0x41, 0x5B) if c in cm)
    name = f["name"].getDebugName(4) or ""
    f.close()
    return n, latin, name


# U+200F (RLM) is the ONLY safe way to force an RTL paragraph base on a line whose
# first STRONG character is Latin (a brand, or a runtime-substituted {VAR}). But the
# shipped faces have NO glyph for it, so a bare RLM would draw `.notdef` = a TOFU BOX
# -- the documented Spider-Man 2 trap. So map the whole bidi-control set to ONE
# zero-width, zero-contour glyph.
BIDI_CONTROLS = (0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x061C)


def _add_empty_controls(tgt):
    """Map every bidi control char to a zero-width, zero-contour glyph so it is
    invisible instead of tofu. Returns how many codepoints were mapped."""
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    if "glyf" not in tgt:
        return 0
    name = "bidi_zero"
    if name not in tgt["glyf"]:
        tgt["glyf"][name] = TTGlyphPen(glyphSet=None).glyph()   # no contours
        tgt["hmtx"][name] = (0, 0)                              # zero advance
        order = tgt.getGlyphOrder()
        if name not in order:
            order.append(name)
            tgt.setGlyphOrder(order)
    n = 0
    for t in tgt["cmap"].tables:
        if not t.isUnicode():
            continue
        for cp in BIDI_CONTROLS:
            t.cmap[cp] = name
            n += 1
    return len(BIDI_CONTROLS)


def inject_one(src_ufont, dst_ufont, donor_path):
    sfnt = cc_ufont.read(src_ufont)
    tgt = TTFont(io.BytesIO(sfnt))
    src = TTFont(donor_path)
    added, skipped = anno_font._add_hebrew(tgt, src)
    ctrls = _add_empty_controls(tgt)
    buf = io.BytesIO()
    tgt.save(buf)
    src.close()
    tgt.close()
    out = buf.getvalue()
    cc_ufont.write(dst_ufont, out)
    return added, skipped, out


def inject_dir(src_root, dst_root):
    rows = []
    for dirpath, _dirs, files in os.walk(src_root):
        for fn in files:
            if not fn.lower().endswith(".ufont"):
                continue
            donor = DONORS.get(fn.lower())
            if donor is None:
                continue  # CJK fallback faces: not part of a Hebrew build
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dst_root, rel)
            added, skipped, out = inject_one(src, dst, donor)
            heb, latin, name = hebrew_coverage(out)
            rows.append((rel, added, heb, latin, name, len(out)))
            print("  %-44s +%3d glyphs  -> %2d/27 heb  %2d/26 latin  +%d bidi-ctrl  [%s]"
                  % (fn, added, heb, latin, len(BIDI_CONTROLS), name))
    return rows


def check_dir(root):
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            if not fn.lower().endswith(".ufont"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                heb, latin, name = hebrew_coverage(cc_ufont.read(p))
                print("  %2d/27 heb  %2d/26 latin  %-44s [%s]" % (heb, latin, fn, name))
            except Exception as e:
                print("  ERR", fn, e)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        check_dir(argv[2])
        return 0
    if cmd == "inject":
        rows = inject_dir(argv[2], argv[3])
        bad = [r for r in rows if r[2] != 27 or r[3] != 26]
        print("\n%d faces injected, %d defective" % (len(rows), len(bad)))
        return 1 if bad or not rows else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
