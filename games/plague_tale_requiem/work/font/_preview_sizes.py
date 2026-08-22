# -*- coding: utf-8 -*-
"""Decide the SIZE offline against the user's REAL English reference.

The user keeps saying the Hebrew is "too big" even though it already matches the English CAP
height (69 px). The reason is that English UI text is mostly lowercase, so the size a reader
perceives is the X-HEIGHT (~51 px), while Hebrew has no lowercase and fills the full cap. This
stacks the ACTUAL English word from the user's screenshot beside Hebrew rendered at several atlas
ink sizes (upscaled x3.31 the way the engine does), so the matching size is read off ONE image
instead of a game launch.

    python _preview_sizes.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from build_hebrew_font import SS, DEF_FONT, SC

UP = 3.31                       # screenshot-scale magnification (atlas 26 -> 86 on screen)
WORD = "שפת הכתוביות"
EN_REF = r"C:\Users\Nehoray_Cohen\Desktop\תמונה1.png"
SIZES = [21, 17, 15, 13]        # atlas ink px  -> screen 69 / 56 / 50 / 43
PARCH = np.array([228, 223, 212], np.float32)
INK = np.array([40, 33, 26], np.float32)


def render_word(size):
    W, H, BL = 160, 200, 130
    f = ImageFont.truetype(DEF_FONT, size * SS)
    glyphs = []
    for ch in reversed(WORD):           # visual order
        if ch == " ":
            glyphs.append(None); continue
        im = Image.new("L", (W * SS, H * SS), 0)
        ImageDraw.Draw(im).text((10 * SS, BL * SS), ch, fill=255, font=f, anchor="ls")
        a = np.array(im.resize((W, H), Image.LANCZOS)).astype(np.float32)
        a = np.clip((a - 22.0) * 1.90, 0, 255); a[a < 10] = 0
        ys, xs = np.where(a > 10)
        glyphs.append(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    h = max((g.shape[0] for g in glyphs if g is not None)) + 8
    w = sum((g.shape[1] + 4) if g is not None else 12 for g in glyphs) + 20
    can = np.zeros((h, w), np.float32)
    x = 10
    for g in glyphs:
        if g is None:
            x += 12; continue
        can[h - 4 - g.shape[0]:h - 4, x:x + g.shape[1]] = g
        x += g.shape[1] + 4
    big = np.array(Image.fromarray(can.astype(np.uint8)).resize(
        (int(w * UP), int(h * UP)), Image.BILINEAR)).astype(np.float32) / 255
    comp = PARCH[None, None] * (1 - big[..., None]) + INK[None, None] * big[..., None]
    return Image.fromarray(comp.clip(0, 255).astype(np.uint8), "RGB")


# --- crop the English half of the reference (left of the separator bar) ---
en = None
if os.path.exists(EN_REF):
    ea = np.array(Image.open(EN_REF).convert("L"))
    ink = ea < 140
    bar = np.where(ink.mean(axis=0) > 0.9)[0]
    xcut = bar.min() if len(bar) else ea.shape[1]
    rgb = np.array(Image.open(EN_REF).convert("RGB"))[:, :xcut]
    # trim to the ink rows
    rows = np.where((np.array(Image.fromarray(rgb).convert("L")) < 140).mean(axis=1) > 0.003)[0]
    if len(rows):
        rgb = rgb[max(0, rows.min() - 8):rows.max() + 8]
    en = Image.fromarray(rgb)

rows = []
if en is not None:
    rows.append(("ENGLISH reference (the target visual size)", en))
for s in SIZES:
    rows.append((f"Hebrew  atlas {s}px  ->  {s * UP:.0f}px on screen", render_word(s)))

W = max(im.width for _, im in rows) + 20
H = sum(im.height + 26 for _, im in rows) + 10
sheet = Image.new("RGB", (W, H), (235, 231, 220))
dr = ImageDraw.Draw(sheet)
y = 6
for label, im in rows:
    sheet.paste(im, (10, y))
    dr.text((12, y + im.height + 4), label, fill=(150, 30, 30))
    y += im.height + 26
out = os.path.join(SC, "SIZE_COMPARE.png")
sheet.save(out)
print("wrote", out)
print("screen heights:", {s: round(s * UP) for s in SIZES}, " English cap=69 x-height=51")
