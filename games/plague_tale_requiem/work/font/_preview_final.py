# -*- coding: utf-8 -*-
"""OFFLINE preview of the FINAL look: a real subtitle line at the shipping body height, drawn
the way the game composites it (white ink over the colour channel used as a black outline), for
several weights at once — so a weight change never costs a game restart.
See [[minimize-game-restarts]]."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from build_hebrew_font import (LADDER_INK, GLOW_D0, ramp_len, _dist_from_ink, INK_GRAY,
                               EDGE_SOFT, SS, SC)

TXT = "הוא נמצא מאחורינו, אמיסיה! הוא הולך לתפוס אותנו"
BODY = LADDER_INK[0]
ZOOM = 3                       # the atlas is 1:1 with the screen; zoom only so we can SEE it
CANDS = [("Assistant-Light  10.0%   << DEPLOYED", r"C:\Windows\Fonts\Assistant-Light.ttf"),
         ("Assistant-Regular 12.5%", r"C:\Windows\Fonts\Assistant-Regular.ttf"),
         ("Heebo-Light 10.0%", r"C:\Windows\Fonts\Heebo-Light.ttf"),
         ("FrankRuhlLibre-Medium 10.0%", r"C:\Windows\Fonts\FrankRuhlLibre-Medium.ttf")]
W, H = 640, 60


def coverage(path):
    for s in range(BODY, BODY * 4):
        b = ImageFont.truetype(path, s).getbbox("מ")
        if (b[3] - b[1]) >= BODY:
            break
    f = ImageFont.truetype(path, s * SS)
    im = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(im).text((W * SS - 20 * SS, 42 * SS), TXT, fill=255, font=f, anchor="rs")
    im = im.resize((W, H), Image.LANCZOS)
    if EDGE_SOFT > 0:
        im = im.filter(ImageFilter.GaussianBlur(EDGE_SOFT))
    a = np.clip((np.array(im, np.float32) - 6.0) * 1.10, 0, 255)
    a[a < 4] = 0
    return a


def composite(a):
    """what the shader shows: black outline (alpha = the ramp) then white ink on top."""
    d = _dist_from_ink(a > 128, 12)
    rl = ramp_len(BODY)
    outline = np.clip(GLOW_D0 * (1.0 - d.astype(np.float32) / rl), 0, 255) / 255.0
    ink = a / 255.0
    bg = np.array([96, 104, 96], np.float32)          # a mid game background
    img = bg[None, None] * np.ones((H, W, 1), np.float32)
    img = img * (1 - outline[..., None])                                  # black outline
    img = img * (1 - ink[..., None]) + np.array([245, 245, 240])[None, None] * ink[..., None]
    return img.clip(0, 255).astype(np.uint8)


rows = [composite(coverage(p)) for _, p in CANDS]
sheet = Image.new("RGB", (W * ZOOM, (H * ZOOM + 24) * len(rows)), (20, 22, 20))
dr = ImageDraw.Draw(sheet)
lab = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 14)
for i, (img, (name, _)) in enumerate(zip(rows, CANDS)):
    y = i * (H * ZOOM + 24)
    sheet.paste(Image.fromarray(img).resize((W * ZOOM, H * ZOOM), Image.NEAREST), (0, y))
    dr.text((8, y + H * ZOOM + 4), name, fill=(255, 220, 120), font=lab)
out = os.path.join(SC, "WEIGHT_FINAL.png")
sheet.save(out)
print("body =", BODY, "px   outline =", round(ramp_len(BODY), 1), "px")
print("wrote", out)
