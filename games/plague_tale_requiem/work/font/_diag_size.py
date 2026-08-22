# -*- coding: utf-8 -*-
"""Measure the ORIGINAL Arabic letter ink-heights (the game's intended subtitle size)
so we can calibrate Hebrew BODY_TARGET to render at the same on-screen size."""
import sys
sys.path.insert(0, ".")
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358


def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


def measure(path, label):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    heights, widths = [], []
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if not (c and len(c) == 1 and is_ar(ord(c))):
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        a = decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))[y0:y1, x0:x1]
        ys, xs = np.where(a > 100)
        if len(ys):
            heights.append(ys.max() - ys.min() + 1)
            widths.append(xs.max() - xs.min() + 1)
    h = np.array(heights)
    print(f"{label}: n={len(h)}  ink-height median={np.median(h):.0f} "
          f"p25={np.percentile(h,25):.0f} p75={np.percentile(h,75):.0f} "
          f"max={h.max()} min={h.min()}")
    return h


print("Original Arabic letters render at the game's subtitle/menu size.")
print("Our Hebrew BODY_TARGET should match their INK-height so sizes match.\n")
measure(DPC + ".he_backup", "ORIG arabic letters")

# our current hebrew for reference
D = DpcRepack(DPC)
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
m2t = resolve_mat_textures(byid, fz)
hh = []
for e in fz.entries:
    c = cid_to_char(e.cid)
    if c and len(c) == 1 and 0x05D0 <= ord(c) <= 0x05EA:
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        a = decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))[y0:y1, x0:x1]
        ys, _ = np.where(a > 100)
        if len(ys): hh.append(ys.max() - ys.min() + 1)
hh = np.array(hh)
print(f"OUR hebrew (BODY_TARGET=40): n={len(hh)} ink-height median={np.median(hh):.0f} "
      f"max={hh.max()} min={hh.min()}")
