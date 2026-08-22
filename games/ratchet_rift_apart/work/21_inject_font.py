"""Inject Hebrew into R&C's Proxima Nova Regular+Bold (extracted by 20_font_extract.py).
Reuse anno_font._add_hebrew (glyf/hmtx/cmap merge from a Heebo donor, strips vertical
metrics, sets OS/2 Hebrew bits), then ADD a zero-width empty glyph for U+200F/U+200E
(so the &rlm; bidi anchors used by the LOGICAL build render INVISIBLE, never .notdef
tofu — the SM2 lesson). Proxima Nova is a clean Latin/Cyrillic glyf TTF, so the merge
is straightforward. Output: work/fonts/*_he.ttf (the raw TTF blobs the applier deploys)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "anno1800", "work"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
import anno_font

FONTS = os.path.join(HERE, "fonts")
HEEBO = os.path.join(ROOT, "games", "spiderman2", "extracted", "_heebo")
PAIRS = [
    ("proximanova_regular_normal.ttf", os.path.join(HEEBO, "Heebo-Regular.ttf")),
    ("proximanova_bold_normal.ttf",    os.path.join(HEEBO, "Heebo-Bold.ttf")),
]
BIDI_CONTROLS = [0x200F, 0x200E, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E]  # RLM/LRM/embed/override/pop

def add_empty_controls(tgt):
    """Map every bidi control char to ONE zero-width, zero-contour glyph so
    LOGICAL+&rlm; anchors are invisible instead of tofu."""
    if "glyf" not in tgt:
        return 0
    name = "bidi_empty"
    if name not in tgt["glyf"]:
        pen = TTGlyphPen(glyphSet=None)          # no contours
        tgt["glyf"][name] = pen.glyph()
        tgt["hmtx"][name] = (0, 0)
        order = tgt.getGlyphOrder()
        if name not in order:
            order.append(name); tgt.setGlyphOrder(order)
    n = 0
    for t in [c for c in tgt["cmap"].tables if c.isUnicode()]:
        for cp in BIDI_CONTROLS:
            t.cmap[cp] = name; n += 1
    return n

for target_name, heebo_src in PAIRS:
    tp = os.path.join(FONTS, target_name)
    if not os.path.exists(tp):
        print(f"[!] missing {tp} — run 20_font_extract.py first"); continue
    tgt = TTFont(tp)
    upem_t = tgt["head"].unitsPerEm
    src = TTFont(heebo_src)
    upem_s = src["head"].unitsPerEm
    before = sum(1 for cp in range(0x05D0,0x05EB) if cp in tgt.getBestCmap())
    added, skipped = anno_font._add_hebrew(tgt, src)
    ctl = add_empty_controls(tgt)
    outp = os.path.join(FONTS, target_name.replace(".ttf", "_he.ttf"))
    tgt.save(outp)
    # verify
    v = TTFont(outp)
    heb = sum(1 for cp in range(0x05D0,0x05EB) if cp in v.getBestCmap())
    lat = sum(1 for cp in range(0x41,0x5B) if cp in v.getBestCmap())
    rlm = 0x200F in v.getBestCmap()
    print(f"[+] {target_name}: upem tgt={upem_t} heebo={upem_s} | Hebrew before={before} added={added} skipped={skipped} "
          f"| controls mapped={ctl} | VERIFY heb {heb}/27, latin {lat}/26, rlm-mapped={rlm} -> {os.path.basename(outp)} ({os.path.getsize(outp)} B)")
