#!/usr/bin/env python3
"""
Bake Hebrew glyphs into the game's SDF glyph-atlas format, from a chosen TTF.

Why re-bake instead of keeping the copied Thai-mod glyphs: measured against the SAME atlas,
the copied Hebrew has 20 px ink height while the native Latin CAP is 28 px — the Hebrew is
29 % too small (ratio 0.71 where the calibration rule wants Hebrew body == native cap).
And the game's own UI face, AvenirNextWorld, already contains all 27 Hebrew letters, so
baking from it matches the game's typography exactly instead of importing a foreign face.

SDF parameters (measured from the shipped atlas, not guessed):
    value = clamp(0, 255, round(128 + 16 * d))     d = signed distance in px, + = inside
    edge = 128, slope = 16/px, spread = 8 px, box = ink bbox expanded by 9 px per side

    python work/bake_hebrew_sdf.py preview        # offline comparison sheet, no game needed
"""
import os
import sys
import math

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.environ.get("ACBF_GAME", r"C:\Games\Assassin's Creed Black Flag Resynced"),
                   "resources")

HEB = [chr(c) for c in range(0x05D0, 0x05EB)]
EDGE, SLOPE, SPREAD, PAD = 128, 16.0, 8, 9
NATIVE_CAP = 28          # measured: Latin CAP ink height in the Arabic atlas


EM_PX = 40               # the atlas's own pixelSize (GFOF+0x10) — render at the game's scale


def em_for_cap(font_path, target=None):
    """Hebrew is SHORTER than Latin caps at the same em, so rendering at the atlas's 40 px
    gives only ~23 px of ink. Scale the em so the Hebrew ink height equals the native Latin
    CAP height (the calibration rule: Hebrew body == native cap)."""
    from PIL import ImageFont
    target = target or NATIVE_CAP
    f = ImageFont.truetype(font_path, EM_PX)
    bb = f.getbbox("אבדהם")
    ih = max(1, bb[3] - bb[1])
    return max(8, int(round(EM_PX * target / ih)))


def bake(font_path, px=None):
    px = px or em_for_cap(font_path)
    """Bake every Hebrew letter into the atlas's record convention, measured from the
    shipped Latin records (verified against the TTF's own metrics at 40 px):

        advance      = the FONT's advance at EM_PX   (NOT the ink width - using the ink
                       width made letters overlap, because the drawn box is 18 px wider
                       than the ink and the pen then advanced by too little)
        x0,y0,x1,y1  = the ink bbox in glyph space (baseline = 0, y up) expanded by PAD
        W,H          = round(x1-x0), round(y1-y0)
        raster       = SDF, value = clamp(0,255, 128 + 16*d)

    -> {char: (advance, x0, y0, x1, y1, W, H, bytes)}
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    try:
        from scipy.ndimage import distance_transform_edt as edt
    except Exception:
        return None
    SS = 8
    f_small = ImageFont.truetype(font_path, px)
    f_big = ImageFont.truetype(font_path, px * SS)
    out = {}
    for ch in HEB:
        adv = f_small.getlength(ch)
        # render supersampled with the baseline at a known position
        pad_ss = 6 * SS
        W_ss, H_ss = int(px * SS * 3), int(px * SS * 3)
        im = Image.new("L", (W_ss, H_ss), 0)
        ox, oy = pad_ss, int(px * SS * 2)          # pen x, baseline y
        ImageDraw.Draw(im).text((ox, oy), ch, font=f_big, fill=255, anchor="ls")
        bb = im.getbbox()
        if not bb:
            continue
        # ink bbox in 1x glyph space, baseline = 0, y up
        ink_l = (bb[0] - ox) / SS
        ink_r = (bb[2] - ox) / SS
        ink_t = (oy - bb[1]) / SS
        ink_b = (oy - bb[3]) / SS
        x0, x1 = ink_l - PAD, ink_r + PAD
        y0, y1 = ink_b - PAD, ink_t + PAD
        W, H = int(round(x1 - x0)), int(round(y1 - y0))
        # SUB-PIXEL distance field: run the EDT on the SUPERSAMPLED mask and divide by SS,
        # then block-average down to 1x. Computing it on a 1x binary mask quantises every
        # distance to a whole pixel, which leaves only ~32 levels in the AA band (the shipped
        # glyphs have ~71) — that reads in-game as hard, blocky, "upscaled low-res" edges.
        crop = im.crop(bb)
        inside_ss = np.zeros((H * SS, W * SS), dtype=bool)
        y_off = int(round((y1 - ink_t) * SS))
        x_off = int(round((ink_l - x0) * SS))
        a = np.array(crop) >= 128
        ih, iw = a.shape
        ys = slice(max(0, y_off), min(H * SS, y_off + ih))
        xs = slice(max(0, x_off), min(W * SS, x_off + iw))
        inside_ss[ys, xs] = a[:ys.stop - ys.start, :xs.stop - xs.start]
        d_ss = np.where(inside_ss, edt(inside_ss) - 0.5, -(edt(~inside_ss) - 0.5)) / SS
        d = d_ss.reshape(H, SS, W, SS).mean(axis=(1, 3))     # block-average -> smooth 1x field
        v = np.clip(np.round(EDGE + SLOPE * d), 0, 255).astype(np.uint8)
        out[ch] = (adv, x0, y0, x1, y1, W, H, v.tobytes())
    return out


def preview():
    """Render a side-by-side sheet: current copied glyphs vs the game's own face, sized right."""
    from PIL import Image, ImageDraw
    import json, struct
    sys.path.insert(0, HERE)
    import acbf_gfof as G

    rows = []
    # (a) what is in the game right now
    buf = open(os.path.join(HERE, "heatlas", "88c902b3.bin"), "rb").read()
    info = G.parse(buf); g = info["gfof"]
    cm = json.load(open(os.path.join(HERE, "carrier_map.json")))
    carriers = {int(v, 16): int(k, 16) for k, v in cm.items()}
    cur = {}
    for r in info["faces"][0]["recs"]:
        if r[0] in carriers:
            w, h = int(r[6]), int(r[7])
            cur[chr(carriers[r[0]])] = (w, h, G.raster(buf, g, r))
    rows.append(("current (Thai mod, 20px)", cur))

    # (b) the game's own face at the correct size
    for name, px in (("AvenirNextWorld-Light.ttf", NATIVE_CAP),
                     ("AvenirNextWorld-Regular.ttf", NATIVE_CAP),
                     ("AvenirNextWorld-Medium.ttf", NATIVE_CAP),
                     ("AvenirNextWorld-Demi.ttf", NATIVE_CAP)):
        p = os.path.join(RES, name)
        if not os.path.isfile(p):
            continue
        b = bake(p, px)
        if b:
            rows.append((f"{name.replace('AvenirNextWorld-','').replace('.ttf','')} @ {px}px", b))

    cellw, cellh = 46, 60
    sheet = Image.new("L", (cellw * len(HEB) + 260, cellh * len(rows) + 20), 0)
    d = ImageDraw.Draw(sheet)
    for ri, (label, gl) in enumerate(rows):
        y = 10 + ri * cellh
        d.text((6, y + cellh // 2 - 6), label[:30], fill=200)
        for ci, ch in enumerate(HEB):
            if ch not in gl:
                continue
            w, h, data = gl[ch]
            im = Image.frombytes("L", (w, h), bytes(data))
            im = im.point(lambda v: 255 if v >= EDGE else 0)     # show the actual shape
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            sheet.paste(im, (250 + ci * cellw, y + (cellh - im.height) // 2))
    out = os.path.join(HERE, "_font_preview.png")
    sheet.save(out)
    print("wrote", out)
    for label, gl in rows:
        hs = []
        for ch, (w, h, data) in gl.items():
            im = Image.frombytes("L", (w, h), bytes(data)).point(lambda v: 255 if v >= EDGE else 0)
            bb = im.getbbox()
            if bb:
                hs.append(bb[3] - bb[1])
        if hs:
            hs.sort()
            print(f"  {label:34s} median ink height = {hs[len(hs)//2]}px "
                  f"(native Latin CAP = {NATIVE_CAP}px)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    preview()
