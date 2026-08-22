# -*- coding: utf-8 -*-
"""Diagnose the 'black background box' the shader shows behind our glyphs.
Compares OUR deployed glyph vs the ORIGINAL Arabic glyph in the SAME atlas box:
alpha profile + a simulated outline-dilation (what a subtitle-outline shader does)."""
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageFilter
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import (decode_alpha, decode_color, resolve_mat_textures,
                               NPIX, SIDE, HEBREW)

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
os.makedirs(SC, exist_ok=True)


def load(path):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    return byid, fz, m2t


def page(byid, tex):
    raw = byid[tex].body
    return decode_alpha(bytearray(raw[:NPIX])), decode_color(bytearray(raw[:NPIX]))


def outline_sim(alpha):
    """simulate a subtitle outline: dilate the coverage a few px, count the black ring."""
    cov = (alpha > 30).astype(np.uint8) * 255
    dil = np.array(Image.fromarray(cov).filter(ImageFilter.MaxFilter(5)))
    ring = ((dil > 0) & (cov == 0)).sum()
    return ring


dep_byid, dep_fz, dep_m2t = load(DPC)
bak_byid, bak_fz, bak_m2t = load(DPC + ".he_backup")

# pick a few Hebrew entries in the deployed font + a couple digits
targets = []
for e in dep_fz.entries:
    c = cid_to_char(e.cid)
    if c in ("ה", "ש", "מ", "0", "5", "A"):
        targets.append((c, e))

print(f"{'ch':>3} {'box(x0,y0,x1,y1)':>22} {'a_max':>5} {'a_mean_in_box':>13} "
      f"{'aa_frac':>7} {'bg_corner':>9} {'outline_ring':>12}")
rows = []
for c, e in targets:
    tex = dep_m2t[e.mat]
    a, g = page(dep_byid, tex)
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    # expand a few px to catch any halo OUTSIDE the tight glyph box
    X0, Y0, X1, Y1 = max(0, x0 - 6), max(0, y0 - 6), min(SIDE, x1 + 6), min(SIDE, y1 + 6)
    box = a[Y0:Y1, X0:X1]
    amax = int(box.max())
    amean = float(box.mean())
    solid = int((box > 200).sum())
    mid = int(((box > 20) & (box <= 200)).sum())
    aa = mid / max(1, solid)
    # background = mean alpha in the OUTER 2px ring of the expanded box (should be ~0)
    ring = np.concatenate([box[:2].ravel(), box[-2:].ravel(),
                           box[:, :2].ravel(), box[:, -2:].ravel()])
    bg = float(ring.mean())
    orn = outline_sim(box)
    rows.append((c, e, tex, X0, Y0, X1, Y1))
    print(f"{c:>3} {str((x0,y0,x1,y1)):>22} {amax:>5} {amean:>13.1f} "
          f"{aa:>7.2f} {bg:>9.2f} {orn:>12}")
    # dump alpha + color pngs for the glyph, both deployed and (same box) backup
    Image.fromarray(a[Y0:Y1, X0:X1], "L").save(os.path.join(SC, f"bg_{c}_dep_alpha.png"))
    Image.fromarray(g[Y0:Y1, X0:X1].astype(np.uint8), "L").save(
        os.path.join(SC, f"bg_{c}_dep_color.png"))
    ba, bg2 = page(bak_byid, bak_m2t[e.mat])
    Image.fromarray(ba[Y0:Y1, X0:X1], "L").save(os.path.join(SC, f"bg_{c}_bak_alpha.png"))

print("\nPNGs in scratchpad: bg_<ch>_dep_alpha/color + bg_<ch>_bak_alpha")
