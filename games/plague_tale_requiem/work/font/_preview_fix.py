# -*- coding: utf-8 -*-
"""Offline A/B of the CURRENT 7px build vs candidate fixes, each through the REAL DXT5 alpha
codec, magnified 1.65x (1080p fullscreen) AND 3.4x (windowed, what the user is running).
Decides weight + curve + spacing BEFORE spending a game launch."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from build_hebrew_font import enc_alpha, decode_alpha, SS, SC

WORD = "שפת הכתוביות"          # a real menu label with mixed letter shapes
PARCH = np.array([228, 223, 212], np.float32)
DK = np.array([40, 33, 26], np.float32)
FIXED_GAP = 2.6               # engine's fixed inter-glyph component (atlas px)

REG = r"C:\Windows\Fonts\Assistant-Regular.ttf"
SEMI = r"C:\Windows\Fonts\Assistant-SemiBold.ttf"
LIGHT = r"C:\Windows\Fonts\Assistant-Light.ttf"

# (label, font, ink, curve(sub,mul), floor, bx)
CANDS = [
    ("CURRENT  SemiBold 7px  (a-22)*3.6  bx0",      SEMI,  7, (22, 3.6), 14, 0.0),
    ("A  Regular 9px  (a-14)*2.0  bx-1.0",          REG,   9, (14, 2.0),  8, -1.0),
    ("B  Regular 9px  (a-16)*1.6  bx-1.0 (soft AA)",REG,   9, (16, 1.6),  6, -1.0),
    ("C  Light   9px  (a-14)*1.9  bx-1.0",          LIGHT, 9, (14, 1.9),  8, -1.0),
]


def fit_body(path, target):
    for s in range(max(6, target), target * 4):
        b = ImageFont.truetype(path, s).getbbox("מ")
        if (b[3] - b[1]) >= target:
            return s
    return target * 2


def glyph(path, ink, curve, floor, ch):
    size = fit_body(path, ink)
    f = ImageFont.truetype(path, size * SS)
    im = Image.new("L", (160 * SS, 200 * SS), 0)
    ImageDraw.Draw(im).text((10 * SS, 130 * SS), ch, fill=255, font=f, anchor="ls")
    a = np.array(im.resize((160, 200), Image.LANCZOS)).astype(np.float32)
    sub, mul = curve
    a = np.clip((a - sub) * mul, 0, 255)
    a[a < floor] = 0
    ys, xs = np.where(a > 0)
    if not len(ys):
        return np.zeros((2, 2), np.uint8)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8)


def dxt5_roundtrip(canvas):
    """Pad to 4-multiple, run every 4x4 block through the real DXT5 alpha enc/dec."""
    h, w = canvas.shape
    H = (h + 3) // 4 * 4
    W = (w + 3) // 4 * 4
    pad = np.zeros((H, W), np.uint8)
    pad[:h, :w] = canvas
    out = np.zeros((H, W), np.uint8)
    for by in range(H // 4):
        for bx in range(W // 4):
            cell = pad[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4]
            dec = decode_alpha(enc_alpha(cell), 4, 4)
            out[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4] = dec
    return out[:h, :w]


def build_word(path, ink, curve, floor, bx):
    gs = [None if ch == " " else glyph(path, ink, curve, floor, ch) for ch in reversed(WORD)]
    gap = max(0.5, bx + FIXED_GAP)
    h = max(g.shape[0] for g in gs if g is not None) + 4
    x = 4.0
    positions = []
    for g in gs:
        if g is None:
            x += ink * 0.5
            positions.append(None)
            continue
        positions.append(int(round(x)))
        x += g.shape[1] + gap
    W = int(x) + 4
    can = np.zeros((h, W), np.uint8)
    for g, px in zip(gs, positions):
        if g is None:
            continue
        gh, gw = g.shape
        can[h - 2 - gh:h - 2, px:px + gw] = g
    return dxt5_roundtrip(can)


def magnify(canvas, up):
    h, w = canvas.shape
    big = np.array(Image.fromarray(canvas).resize(
        (max(1, int(w * up)), max(1, int(h * up))), Image.BILINEAR)).astype(np.float32) / 255
    comp = PARCH[None, None] * (1 - big[..., None]) + DK[None, None] * big[..., None]
    return Image.fromarray(comp.clip(0, 255).astype(np.uint8), "RGB")


rows = []
for label, path, ink, curve, floor, bx in CANDS:
    can = build_word(path, ink, curve, floor, bx)
    solid = int((can >= 200).sum())
    im165 = magnify(can, 1.65)
    im340 = magnify(can, 3.40)
    rows.append((label, solid, im165, im340))

PADX = 470
Wmax = max(im1.width + im2.width for _, _, im1, im2 in rows) + PADX + 40
Htot = sum(max(im1.height, im2.height) + 34 for _, _, im1, im2 in rows) + 10
sheet = Image.new("RGB", (Wmax, Htot), (245, 242, 234))
dr = ImageDraw.Draw(sheet)
y = 8
for label, solid, im1, im2 in rows:
    dr.text((8, y), f"{label}", fill=(150, 30, 30))
    dr.text((8, y + 14), f"solid px={solid}", fill=(90, 90, 90))
    dr.text((PADX - 90, y + im1.height // 2 - 6), "1.65x", fill=(60, 60, 60))
    sheet.paste(im1, (PADX, y))
    dr.text((PADX + im1.width + 6, y + im1.height // 2 - 6), "3.4x", fill=(60, 60, 60))
    sheet.paste(im2, (PADX + im1.width + 50, y))
    y += max(im1.height, im2.height) + 34
out = os.path.join(SC, "PREVIEW_FIX.png")
sheet.save(out)
print("wrote", out)
