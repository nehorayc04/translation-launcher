# -*- coding: utf-8 -*-
"""Reproduce a subtitle LINE offline from the DEPLOYED atlas glyphs + their metrics,
then simulate the game's likely alpha render (white fill) + a black outline. If a black
BAND appears from the merged outlines -> it's OUR spacing/alpha; if the glyphs stay
separate on transparent -> the band is the game's own subtitle-background panel."""
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageFilter
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")

D = DpcRepack(DPC)
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
m2t = resolve_mat_textures(byid, fz)
pages = {}
def page(tex):
    if tex not in pages:
        pages[tex] = decode_alpha(bytearray(byid[tex].body[:NPIX]))
    return pages[tex]

ent = {}
for e in fz.entries:
    c = cid_to_char(e.cid)
    if c and len(c) == 1:
        ent[c] = e

# STORED (visual) form of "אמיסיה: תמשיך לרוץ!" — Hebrew stays logical, engine lays RTL.
line = "אמיסיה: תמשיך לרוץ!"
BASE = 130
canvas = np.zeros((170, 640), np.float32)
pen_x = 600            # start at right, move left (RTL)
placed = 0
for ch in line:
    if ch == " ":
        pen_x -= 14
        continue
    e = ent.get(ch)
    if e is None:
        pen_x -= 14
        continue
    a = page(m2t[e.mat])
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    gw, gh = x1 - x0, y1 - y0
    glyph = a[y0:y1, x0:x1].astype(np.float32)
    adv = gw + int(e.bx) + 2               # horizontal advance ~ box_width + bx (+tracking)
    pen_x -= adv
    top = BASE - int(e.adv)                # adv field = topY (line-top -> glyph top)
    py, px = max(0, top), max(0, pen_x)
    h, w = glyph.shape
    canvas[py:py + h, px:px + w] = np.maximum(canvas[py:py + h, px:px + w], glyph)
    placed += 1

cov = (canvas > 30).astype(np.uint8) * 255

# render 1: alpha-only WHITE fill (no outline)
Image.fromarray(canvas.clip(0, 255).astype(np.uint8), "L").save(os.path.join(SC, "line_fill.png"))

# render 2: black outline (dilate) UNDER white fill = the readability style
for r in (3, 5, 7):
    dil = np.array(Image.fromarray(cov).filter(ImageFilter.MaxFilter(r)))
    out = np.zeros((*canvas.shape, 3), np.uint8)
    out[dil > 0] = (20, 20, 20)                 # black outline
    fill = canvas.clip(0, 255).astype(np.uint8)
    for c3 in range(3):
        out[..., c3] = np.maximum(out[..., c3], fill)
    Image.fromarray(out, "RGB").save(os.path.join(SC, f"line_outline_r{r}.png"))

# how "filled" does the outline make the text region? (band detector)
band = None
for r in (3, 5, 7):
    dil = np.array(Image.fromarray(cov).filter(ImageFilter.MaxFilter(r)))
    ys, xs = np.where(cov > 0)
    if len(ys):
        bb = dil[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        frac = (bb > 0).mean()
        print(f"outline r={r}: text-bbox coverage after dilation = {frac*100:.0f}% "
              f"({'MERGES INTO A BAND' if frac > 0.75 else 'stays separate'})")
print(f"placed {placed} glyphs; PNGs: line_fill.png, line_outline_r3/5/7.png")
