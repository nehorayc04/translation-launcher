"""Prove the rebuilt font BEFORE it ever touches the game.

Two independent checks, both offline:
  1. ROUND-TRIP: hebrew.ffd -> .fnt (at the NEW 1024x2048 dims) must reproduce every
     ORIGINAL glyph's metrics exactly, and carry all 27 Hebrew letters.  The .ffd stores
     normalised UVs, so a height-rescale mistake would shift every shipped glyph -- this
     is the check that catches it.
  2. RENDER: decode the rebuilt atlas and draw real words from the NEW metrics (Hebrew,
     Latin and Arabic side by side), so the result is judged without launching anything.

  python -u verify_font.py
"""
import sys, os, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "extract"))
FFD = os.path.abspath(os.path.join(HERE, "..", "..", "watchdogs2", "tools", "ffdconverter",
                                   "FFDConverter.exe"))
sys.path.insert(0, HERE)
from fc5_font import parse_fnt, Atlas, ATLAS_W, ORIG_H, NEW_H

# 1 -------------------------------------------------------------- round-trip
rt = os.path.join(OUT, "hebrew_roundtrip.fnt")
if os.path.exists(rt):
    os.remove(rt)
p = subprocess.run([FFD, "--ffd2fnt", "-v", "FC5", "-f", os.path.join(OUT, "hebrew.ffd"),
                    "-o", rt], input=f"{ATLAS_W}\n{NEW_H}\n\n", capture_output=True, text=True)
assert os.path.exists(rt), p.stdout + p.stderr

orig = parse_fnt(os.path.join(OUT, "arabic.fnt"))
back = parse_fnt(rt)
heb = [c for c in range(0x05D0, 0x05EB) if c in back]
drift = max((max(abs(a - b) for a, b in zip(o, back[cp])) if cp in back else 999.0)
            for cp, o in orig.items())
print(f"original {len(orig)} glyphs -> round-tripped {len(back)}   hebrew {len(heb)}/27")
print(f"max metric drift over the {len(orig)} shipped glyphs: {drift:.3f}")
print("  ROUND-TRIP", "OK" if drift < 1e-6 and len(heb) == 27 else "FAILED")

# 2 -------------------------------------------------------------- render
at = Atlas(os.path.join(OUT, "hebrew.xbt"))
src = Atlas(os.path.join(OUT, "arabic_atlas.xbt"))
print(f"\nrebuilt atlas {at.w}x{at.h}, {at.mips} mips")
print(f"  original rows identical: {(at.mip0[:ORIG_H] == src.mip0).all()}")
print(f"  new rows alpha mean {at.mip0[ORIG_H:].mean():.2f} max {at.mip0[ORIG_H:].max()}")

B = json.load(open(os.path.join(OUT, "hebrew_build.json")))
EDGE = B["sdf_offset"]     # the SDF threshold the UI shader uses (= the fitted offset)
UPX = B["adv_units_per_px"]  # advance units per atlas pixel, from the build


def draw(text, y0, canvas, rtl=False):
    """Lay text out with the NEW metrics, the way the engine would."""
    pen = 10.0
    seq = text[::-1] if rtl else text
    for chx in seq:
        cp = ord(chx)
        if cp not in back:
            pen += 14; continue
        x, y, w, h, xo, yo, adv = back[cp]
        if w > 0:
            g = Image.fromarray(at.mip0[int(round(y)):int(round(y + h)),
                                        int(round(x)):int(round(x + w))])
            g = g.point(lambda v: 255 if v >= EDGE else 0)
            canvas.paste(g, (int(round(pen + xo)), int(round(y0 + yo))), g)
        pen += adv / UPX                                    # game units -> atlas px
    return pen


canvas = Image.new("L", (900, 200), 0)
draw("שלום עברית", 10, canvas, rtl=True)          # visual order == what the engine draws
draw("MENU Options 123", 60, canvas)
draw("العربية", 110, canvas, rtl=True)
draw("אבגדהוזחטיכלמנסעפצקרשת", 150, canvas, rtl=True)
canvas.save(os.path.join(OUT, "hebrew_word.png"))
print(f"  wrote hebrew_word.png (Hebrew / Latin / Arabic drawn from the new metrics)")
