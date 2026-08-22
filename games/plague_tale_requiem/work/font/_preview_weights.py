# -*- coding: utf-8 -*-
"""OFFLINE weight/shape comparison. The engine FIXES the on-screen glyph HEIGHT (it normalizes
every font to the same requested size), so what actually differs on screen between fonts is the
STROKE WEIGHT + shape. Render each candidate at the SAME cap height on a dark subtitle band so
the user can pick the weight from ONE image — no game restart needed."""
import os
from PIL import Image, ImageDraw, ImageFont

FONTS = [
    ("Heebo Thin",        r"C:\Windows\Fonts\Heebo-Thin.ttf"),
    ("Heebo Light",       r"C:\Windows\Fonts\Heebo-Light.ttf"),
    ("Heebo Regular",     r"C:\Windows\Fonts\Heebo-Regular.ttf"),
    ("Heebo Medium (current)", r"C:\Windows\Fonts\Heebo-Medium.ttf"),
    ("Assistant Light",   r"C:\Windows\Fonts\Assistant-Light.ttf"),
    ("Assistant Regular", r"C:\Windows\Fonts\Assistant-Regular.ttf"),
    ("Rubik Light",       r"C:\Windows\Fonts\Rubik-Light.ttf"),
    ("Alef Regular",      r"C:\Windows\Fonts\Alef-regular.ttf"),
]
# a human-readable RTL preview: reverse so PIL (LTR) draws it visually correct
SENT = "אמיסיה והוגו התחבאו מהחיילים בחשכה"[::-1]
ALPH = "אבגדהוזחטיכלמנסעפצקרשת"[::-1]
BODY = 46                    # fixed body height (px) — same for all, mimicking the fixed on-screen size
ROW_H = 150
LABEL_W = 300
W = LABEL_W + 1180

def fit(path, target):
    for s in range(target, target * 3):
        b = ImageFont.truetype(path, s).getbbox("מ")
        if (b[3] - b[1]) >= target:
            return s
    return target * 2

img = Image.new("RGB", (W, ROW_H * len(FONTS) + 10), (24, 22, 20))
dr = ImageDraw.Draw(img)
lab = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 22)
for i, (name, path) in enumerate(FONTS):
    y = i * ROW_H + 5
    # dark rounded subtitle-style band
    dr.rounded_rectangle([LABEL_W, y + 20, W - 20, y + ROW_H - 20], radius=14, fill=(12, 11, 10))
    try:
        f = ImageFont.truetype(path, fit(path, BODY))
    except Exception as e:
        dr.text((LABEL_W + 20, y + 50), f"(missing: {e})", fill=(200, 80, 80), font=lab); continue
    dr.text((16, y + 40), name, fill=(230, 220, 200), font=lab)
    # sentence (top) + alphabet (bottom), light warm ink like the game
    dr.text((W - 40, y + 42), SENT, fill=(232, 226, 214), font=f, anchor="ra")
    dr.text((W - 40, y + 96), ALPH, fill=(232, 226, 214), font=f, anchor="ra")

out = os.path.join(
    r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
    r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
    r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad", "WEIGHT_COMPARE.png")
img.save(out)
print("saved:", out)
