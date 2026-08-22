# -*- coding: utf-8 -*-
"""Pick the alpha CURVE offline, at the size the engine actually shows.

The engine magnifies BIG_ARABIC ~2.8x with bilinear filtering, so the atlas edge profile is not
what the player sees — a soft atlas edge becomes a WIDE mushy edge, and a razor edge becomes
stair-stepping. The only honest way to choose is to render the candidates, upscale them the way
the GPU does, and look at the result. One image replaces a game launch.

    python _preview_curve.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from build_hebrew_font import SS, DEF_FONT, LADDER_INK, fit_body, SC

UP = 2.80                      # measured engine magnification of our atlas glyphs
WORD = "שפת הכתוביות"          # a real menu label
PARCH = np.array([228, 223, 212], np.float32)
INK = np.array([40, 33, 26], np.float32)

# (label, edge_blur_px, subtract, gain, floor)
CURVES = [
    ("current   (a-10)*1.25 blur .15", 0.15, 10.0, 1.25, 6),
    ("crisper   (a-16)*1.55 blur .00", 0.00, 16.0, 1.55, 8),
    ("crispest  (a-22)*1.90 blur .00", 0.00, 22.0, 1.90, 10),
    ("softer    (a- 6)*1.10 blur .30", 0.30, 6.0, 1.10, 4),
]


def render(ch, size, blur, sub, gain, floor):
    W, H, BL = 160, 200, 130
    f = ImageFont.truetype(DEF_FONT, size * SS)
    im = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(im).text((10 * SS, BL * SS), ch, fill=255, font=f, anchor="ls")
    im = im.resize((W, H), Image.LANCZOS)
    if blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.clip((np.array(im).astype(np.float32) - sub) * gain, 0, 255)
    a[a < floor] = 0
    ys, xs = np.where(a > 10)
    if not len(ys):
        return np.zeros((4, 4), np.float32)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


size = fit_body(DEF_FONT, LADDER_INK[0])
rows = []
for label, blur, sub, gain, floor in CURVES:
    glyphs = [render(c, size, blur, sub, gain, floor) for c in reversed(WORD) if c != " "]
    h = max(g.shape[0] for g in glyphs) + 8
    w = sum(g.shape[1] + 4 for g in glyphs) + 20
    can = np.zeros((h, w), np.float32)
    x = 10
    for g in glyphs:
        can[h - 4 - g.shape[0]:h - 4, x:x + g.shape[1]] = np.maximum(
            can[h - 4 - g.shape[0]:h - 4, x:x + g.shape[1]], g)
        x += g.shape[1] + 4
    big = np.array(Image.fromarray(can.astype(np.uint8)).resize(
        (int(w * UP), int(h * UP)), Image.BILINEAR)).astype(np.float32) / 255
    comp = PARCH[None, None] * (1 - big[..., None]) + INK[None, None] * big[..., None]
    img = Image.fromarray(comp.clip(0, 255).astype(np.uint8), "RGB")
    mid = ((can > 30) & (can < 225)).sum(); solid = (can >= 225).sum()
    rows.append((f"{label}   AA mid/solid={mid/max(solid,1):.2f}", img))

W = max(im.width for _, im in rows) + 20
H = sum(im.height + 26 for _, im in rows) + 10
sheet = Image.new("RGB", (W, H), (24, 24, 24))
dr = ImageDraw.Draw(sheet)
y = 6
for label, im in rows:
    sheet.paste(im, (10, y))
    dr.text((12, y + im.height + 4), label, fill=(255, 220, 90))
    y += im.height + 26
out = os.path.join(SC, "CURVE_COMPARE.png")
sheet.save(out)
print("wrote", out)
print("(rendered at the SHIPPING body, then upscaled x%.1f like the GPU)" % UP)
