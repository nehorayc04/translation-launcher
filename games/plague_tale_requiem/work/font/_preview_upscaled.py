# -*- coding: utf-8 -*-
"""Predict the IN-GAME look without launching: take the glyphs from the BUILT atlas, apply the
engine's measured ~2.8x magnification (bilinear, like the GPU), composite the outline, and put a
simulated English line beside it at ITS measured ~1.2x magnification.

Both magnifications come from the user's side-by-side screenshot (_diag_screenshot.py):
  English: atlas x-height 41 -> 51 px on screen (x1.24)
  Hebrew : atlas ink     26 -> 86 px on screen (x3.31 in screenshot units)
Normalising to the English scale, the engine magnifies our BIG_ARABIC glyphs ~2.8x more than it
magnifies its own menu font — THAT is the whole quality gap, and it is a property of the font the
Arabic slot is forced to use, not of our rasterisation. See [[minimize-game-restarts]].
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import (decode_alpha, decode_color, resolve_mat_textures, NPIX, BIG, SC,
                               LADDER_INK, DEF_FONT)

BUILT = "_ENGLISH_he.DPC"
HE_UP = 2.80                      # engine magnification of our atlas glyphs (measured)
EN_UP = 1.24                      # the game's own menu font magnification (measured)
WORD = "שפת הכתוביות"
EN_WORD = "Subtitle language"

D = DpcRepack(BUILT)
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
m2t = resolve_mat_textures(byid, fz)
pages = {}
for t in set(m2t.values()):
    raw = byid[t].body
    pages[t] = (decode_alpha(bytearray(raw[:NPIX])), decode_color(bytearray(raw[:NPIX])))
ent = {cid_to_char(e.cid): e for e in fz.entries if cid_to_char(e.cid)}

# --- lay the Hebrew word out from the REAL atlas (visual order: draw reversed) ---
H = 90
canvas_a = np.zeros((H, 900), np.float32)
canvas_c = np.zeros((H, 900), np.float32)
x = 20
base = 70
for ch in reversed(WORD):
    if ch == " ":
        x += 10
        continue
    e = ent.get(ch)
    if e is None:
        continue
    a, g = pages[m2t[e.mat]]
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    ga, gc = a[y0:y1, x0:x1], g[y0:y1, x0:x1]
    h, w = ga.shape
    top = base - h
    canvas_a[top:top + h, x:x + w] = np.maximum(canvas_a[top:top + h, x:x + w], ga)
    canvas_c[top:top + h, x:x + w] = np.maximum(canvas_c[top:top + h, x:x + w], gc)
    x += w + 3
canvas_a = canvas_a[:, :x + 20]
canvas_c = canvas_c[:, :x + 20]


def up(arr, f):
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "L")
    return np.array(im.resize((int(im.width * f), int(im.height * f)), Image.BILINEAR), np.float32)


def compose(alpha, colour, bg=(214, 210, 198), ink=(58, 56, 52)):
    """light parchment menu: the colour channel darkens (outline), then the ink is drawn dark."""
    o = colour / 255.0
    k = alpha / 255.0
    img = np.array(bg, np.float32)[None, None] * np.ones(alpha.shape + (1,), np.float32)
    img = img * (1 - 0.55 * o[..., None])
    img = img * (1 - k[..., None]) + np.array(ink, np.float32)[None, None] * k[..., None]
    return img.clip(0, 255).astype(np.uint8)


he = compose(up(canvas_a, HE_UP), up(canvas_c, HE_UP))

# --- simulated English at its own magnification (x-height 41 atlas -> x1.24) ---
f = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 57)
im = Image.new("L", (700, 90), 0)
ImageDraw.Draw(im).text((20, 70), EN_WORD, fill=255, font=f, anchor="ls")
en_a = up(np.array(im, np.float32), EN_UP)
en = compose(en_a, np.zeros_like(en_a))

W = max(he.shape[1], en.shape[1]) + 20
sheet = Image.new("RGB", (W, he.shape[0] + en.shape[0] + 60), (30, 30, 30))
dr = ImageDraw.Draw(sheet)
lab = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 15)
sheet.paste(Image.fromarray(en), (10, 8))
dr.text((10, en.shape[0] + 12), f"ENGLISH  (game font, x{EN_UP} magnification)  <- the target",
        fill=(255, 220, 120), font=lab)
sheet.paste(Image.fromarray(he), (10, en.shape[0] + 36))
dr.text((10, en.shape[0] + he.shape[0] + 40),
        f"HEBREW  {os.path.basename(DEF_FONT)}  {LADDER_INK[0]}px atlas  x{HE_UP} magnification",
        fill=(255, 220, 120), font=lab)
out = os.path.join(SC, "INGAME_PREDICT.png")
sheet.save(out)
ys = np.where(canvas_a.max(axis=1) > 128)[0]
print(f"hebrew atlas ink height = {ys.max()-ys.min()+1} px -> {(ys.max()-ys.min()+1)*HE_UP:.0f} px on screen")
print("wrote", out)
