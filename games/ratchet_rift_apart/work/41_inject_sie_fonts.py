"""In-game garbage fix (round 2): the SAVE/PROFILE screens + system dialogs render with
the Sony platform Gothic font `SIE-TBGoStd R/B` (found in d\\userinterface, 0 Hebrew),
NOT Proxima Nova — so Hebrew came out as tofu there while the main menu (Proxima Nova,
injected) was fine. [[font-inject-every-face]] — inject EVERY face that renders our text.

Extract the two SIE-TBGoStd faces from the toc, merge Heebo Hebrew (anno_font._add_hebrew)
+ empty the bidi controls, save the raw TTF blobs the applier deploys. The 3 CJK fallbacks
(MElle HK, AsiaKDREAM2) are script-gated — Hebrew never routes to them under the English
slot — so they are deliberately skipped.

    python 41_inject_sie_fonts.py
"""
import os, sys, io

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = r"F:\Game Lab\Ratchet & Clank - Rift Apart"
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.path.insert(0, os.path.join(ROOT, "games", "anno1800", "work"))
sys.path.insert(0, ".venv/Lib/site-packages")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1 as _d1
from fontTools.ttLib import TTFont
import anno_font
import importlib.util
_spec = importlib.util.spec_from_file_location("inj21", os.path.join(HERE, "21_inject_font.py"))
# reuse add_empty_controls without running 21's module body
from fontTools.pens.ttGlyphPen import TTGlyphPen
BIDI_CONTROLS = [0x200F, 0x200E, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E]
def add_empty_controls(tgt):
    if "glyf" not in tgt: return 0
    name = "bidi_empty"
    if name not in tgt["glyf"]:
        tgt["glyf"][name] = TTGlyphPen(glyphSet=None).glyph()
        tgt["hmtx"][name] = (0, 0)
        order = tgt.getGlyphOrder()
        if name not in order: order.append(name); tgt.setGlyphOrder(order)
    n = 0
    for t in [c for c in tgt["cmap"].tables if c.isUnicode()]:
        for cp in BIDI_CONTROLS: t.cmap[cp] = name; n += 1
    return n

FONTS = os.path.join(HERE, "fonts")
HEEBO = os.path.join(ROOT, "games", "spiderman2", "extracted", "_heebo")
# aid -> (output name, Heebo donor). SIE-TBGoStd = Sony platform Gothic Regular/Bold.
TARGETS = {
    0xB927D5EA184444C1: ("sie_gothic_regular_he.ttf", os.path.join(HEEBO, "Heebo-Regular.ttf")),
    0x8187C80EF59344DC: ("sie_gothic_bold_he.ttf",    os.path.join(HEEBO, "Heebo-Bold.ttf")),
}

with open(os.path.join(GAME, "toc"), "rb") as f:
    t = dat1lib.read(f)
t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
t.set_archives_dir(GAME)
assets = t.get_assets_section()
ids = getattr(assets, "ids", None) or getattr(assets, "values", None) or []

def aid_of(x): return int.from_bytes(bytes(x), "little") if not isinstance(x, int) else x

for aid, (outname, donor) in TARGETS.items():
    gi = next((i for i, x in enumerate(ids) if aid_of(x) == aid), None)
    if gi is None:
        print(f"[!] aid 0x{aid:016X} not found"); continue
    data = bytes(t.extract_asset(gi))
    off = 0 if data[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true") else 36
    tgt = TTFont(io.BytesIO(data[off:]))
    before = sum(1 for cp in range(0x05D0, 0x05EB) if cp in tgt.getBestCmap())
    added, skipped = anno_font._add_hebrew(tgt, TTFont(donor))
    ctl = add_empty_controls(tgt)
    outp = os.path.join(FONTS, outname)
    tgt.save(outp)
    v = TTFont(outp)
    heb = sum(1 for cp in range(0x05D0, 0x05EB) if cp in v.getBestCmap())
    lat = sum(1 for cp in range(0x41, 0x5B) if cp in v.getBestCmap())
    print(f"[+] 0x{aid:016X} gi={gi} off={off} | Hebrew before={before} added={added} skipped={skipped} "
          f"| controls={ctl} | VERIFY heb {heb}/27 latin {lat}/26 rlm={0x200F in v.getBestCmap()} "
          f"-> {outname} ({os.path.getsize(outp)} B)")
