"""Render the FC5 menu OFFLINE from the built font, so a size/spacing change costs a
message instead of a game restart ([[minimize-game-restarts]]).

Draws the exact words the user compared against Far Cry 6, using the NEW metrics, beside the
game's own Arabic and Latin from the same atlas -- so the three scripts can be judged at their
true relative sizes.

  python -u preview_menu.py [out.png]
"""
import sys, os, json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "extract")
sys.path.insert(0, HERE)
from fc5_font import Atlas, parse_fnt

at = Atlas(os.path.join(OUT, "hebrew.xbt"))
ch = parse_fnt(os.path.join(OUT, "hebrew_roundtrip.fnt"))
B = json.load(open(os.path.join(OUT, "hebrew_build.json")))
EDGE, UPX = B["sdf_offset"], B["adv_units_per_px"]
SCALE = 1.9                      # the menu is drawn larger than the atlas; scale for viewing


def width(t):
    return sum(ch[ord(c)][6] / UPX for c in t if ord(c) in ch)


def draw(canvas, t, x, y):
    """Lay out one line with the stored metrics (text is already VISUAL, so left to right)."""
    pen = float(x)
    for c in t:
        cp = ord(c)
        if cp not in ch:
            pen += 12; continue
        gx, gy, w, h, xo, yo, adv = ch[cp]
        if w > 0:
            g = Image.fromarray(at.mip0[int(round(gy)):int(round(gy + h)),
                                        int(round(gx)):int(round(gx + w))])
            g = g.point(lambda v: 255 if v >= EDGE else 0)
            canvas.paste(g, (int(round(pen + xo)), int(round(y + yo))), g)
        pen += adv / UPX
    return pen


# stored VISUAL, exactly as the game gets it
from bidi.algorithm import get_display
V = lambda s: get_display(s, base_dir="R")

LINES = [V("המשך משחק"), V("משחק חדש"), V("אפשרויות"),
         V("יציאה לשולחן העבודה"), V("שלום עברית"),
         "خروج إلى"[::-1],      # arabic, the game's own
         "UBISOFT CLUB"]

W, LH = 560, 46
img = Image.new("L", (W, LH * len(LINES) + 20), 0)
y = 8
for t in LINES:
    draw(img, t, (W - width(t)) / 2, y)      # the menu is centre-aligned
    y += LH
img = img.resize((int(W * SCALE), int(img.height * SCALE)), Image.LANCZOS)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "menu_preview.png")
img.save(out)
print(f"body {B['body_px']} px, advance unit {UPX:.4f} -> {out}")
print("  line widths (atlas px): " + ", ".join(f"{width(t):.0f}" for t in LINES))
