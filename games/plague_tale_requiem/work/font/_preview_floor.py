# -*- coding: utf-8 -*-
"""The user asked for a ~70% reduction. Show how small the Hebrew can go and stay legible,
rendered at the 1080p magnification (~1.65x) measured from the real in-game capture.
17 px atlas is the current size; 70% smaller ≈ 5 px."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from build_hebrew_font import SS, DEF_FONT, SC

UP = 28 / 17.0                   # measured in-game at 1920x1080: 17px atlas -> 28px screen
WORD = "לחץ על מקש כלשהו"
SIZES = [17, 13, 11, 9, 7, 5]    # atlas ink px
PARCH = np.array([228, 223, 212], np.float32); DK = np.array([40, 33, 26], np.float32)


def fit_body(path, target):
    for s in range(max(6, target), target * 4):
        if ImageFont.truetype(path, s).getbbox("מ")[3] - ImageFont.truetype(path, s).getbbox("מ")[1] >= target:
            return s
    return target * 2


def word(size):
    f = ImageFont.truetype(DEF_FONT, fit_body(DEF_FONT, size) * SS)
    gs = []
    for ch in reversed(WORD):
        if ch == " ":
            gs.append(None); continue
        im = Image.new("L", (160 * SS, 200 * SS), 0)
        ImageDraw.Draw(im).text((10 * SS, 130 * SS), ch, fill=255, font=f, anchor="ls")
        a = np.array(im.resize((160, 200), Image.LANCZOS)).astype(np.float32)
        a = np.clip((a - 22.0) * 1.90, 0, 255); a[a < 10] = 0
        ys, xs = np.where(a > 10)
        gs.append(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1] if len(ys) else np.zeros((2, 2)))
    h = max(g.shape[0] for g in gs if g is not None) + 6
    w = sum((g.shape[1] + max(1, int(round(size * 0.176)))) if g is not None else int(size * 0.5)
            for g in gs) + 12
    can = np.zeros((h, w), np.float32); x = 6
    for g in gs:
        if g is None:
            x += int(size * 0.5); continue
        can[h - 3 - g.shape[0]:h - 3, x:x + g.shape[1]] = g
        x += g.shape[1] + max(1, int(round(size * 0.176)))
    big = np.array(Image.fromarray(can.astype(np.uint8)).resize(
        (max(1, int(w * UP)), max(1, int(h * UP))), Image.BILINEAR)).astype(np.float32) / 255
    comp = PARCH[None, None] * (1 - big[..., None]) + DK[None, None] * big[..., None]
    return Image.fromarray(comp.clip(0, 255).astype(np.uint8), "RGB")


rows = [(f"atlas {s:2d}px  ->  {s*UP:.0f}px on screen (1080p)"
         + ("   <- CURRENT" if s == 17 else "")
         + ("   <- ~70% smaller" if s == 5 else ""), word(s)) for s in SIZES]
W = max(im.width for _, im in rows) + 260
H = sum(im.height + 10 for _, im in rows) + 10
sheet = Image.new("RGB", (W, H), (235, 231, 220)); dr = ImageDraw.Draw(sheet); y = 6
for label, im in rows:
    sheet.paste(im, (250, y)); dr.text((8, y + im.height // 2 - 6), label, fill=(150, 30, 30))
    y += im.height + 10
out = os.path.join(SC, "FLOOR_COMPARE.png"); sheet.save(out)
print("wrote", out)
