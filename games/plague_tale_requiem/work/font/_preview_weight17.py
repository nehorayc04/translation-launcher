# -*- coding: utf-8 -*-
"""At a SMALLER body the stroke thins, so re-check the weight before shipping 17 px.
Renders the word at atlas ink 17 with several Hebrew fonts, upscaled x3.31 like the engine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

UP = 3.31; SS = 8; INK = 17
WORD = "שפת הכתוביות"
PARCH = np.array([228, 223, 212], np.float32); DK = np.array([40, 33, 26], np.float32)
FONTS = [
    ("Assistant-Regular", r"C:\Windows\Fonts\Assistant-Regular.ttf"),
    ("Assistant-SemiBold", r"C:\Windows\Fonts\Assistant-SemiBold.ttf"),
    ("Heebo-Medium", r"C:\Windows\Fonts\Heebo-Medium.ttf"),
    ("Rubik-Medium", r"C:\Windows\Fonts\Rubik-Medium.ttf"),
]


def fit_body(path, target):
    for s in range(max(6, target), target * 3):
        b = ImageFont.truetype(path, s).getbbox("מ")
        if (b[3] - b[1]) >= target:
            return s
    return target * 2


def word(path):
    size = fit_body(path, INK)
    f = ImageFont.truetype(path, size * SS)
    gs = []
    for ch in reversed(WORD):
        if ch == " ":
            gs.append(None); continue
        im = Image.new("L", (160 * SS, 200 * SS), 0)
        ImageDraw.Draw(im).text((10 * SS, 130 * SS), ch, fill=255, font=f, anchor="ls")
        a = np.array(im.resize((160, 200), Image.LANCZOS)).astype(np.float32)
        a = np.clip((a - 22.0) * 1.90, 0, 255); a[a < 10] = 0
        ys, xs = np.where(a > 10)
        gs.append(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    h = max(g.shape[0] for g in gs if g is not None) + 8
    w = sum((g.shape[1] + 4) if g is not None else 10 for g in gs) + 16
    can = np.zeros((h, w), np.float32); x = 8
    for g in gs:
        if g is None:
            x += 10; continue
        can[h - 4 - g.shape[0]:h - 4, x:x + g.shape[1]] = g; x += g.shape[1] + 4
    # stroke stat
    sw = []
    for yy in range(can.shape[0]):
        run = 0
        for v in can[yy]:
            if v >= 180: run += 1
            elif run: sw.append(run); run = 0
    stroke = np.median(sw) if sw else 0
    big = np.array(Image.fromarray(can.astype(np.uint8)).resize(
        (int(w * UP), int(h * UP)), Image.BILINEAR)).astype(np.float32) / 255
    comp = PARCH[None, None] * (1 - big[..., None]) + DK[None, None] * big[..., None]
    return Image.fromarray(comp.clip(0, 255).astype(np.uint8), "RGB"), stroke, INK


rows = []
for name, path in FONTS:
    if not os.path.exists(path):
        print("skip (missing):", name); continue
    im, st, body = word(path)
    rows.append((f"{name}   stroke {st:.0f}px = {st/body*100:.0f}% of body (English ~12%)", im))

W = max(im.width for _, im in rows) + 20
H = sum(im.height + 26 for _, im in rows) + 10
sheet = Image.new("RGB", (W, H), (235, 231, 220))
dr = ImageDraw.Draw(sheet); y = 6
for label, im in rows:
    sheet.paste(im, (10, y)); dr.text((12, y + im.height + 4), label, fill=(150, 30, 30))
    y += im.height + 26
from build_hebrew_font import SC
out = os.path.join(SC, "WEIGHT17_COMPARE.png"); sheet.save(out)
print("wrote", out)
