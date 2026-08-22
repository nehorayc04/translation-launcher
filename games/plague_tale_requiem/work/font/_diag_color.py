# -*- coding: utf-8 -*-
"""Is the ORIGINAL font's COLOR (BC1/RGB) channel WHITE or a gray glow?
If original = white-on-glyph and ours = gray glow, our color banding is the 'noise'."""
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, decode_color, resolve_mat_textures, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358


def load(path):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    return byid, fz, resolve_mat_textures(byid, fz)


def chans(byid, tex):
    raw = byid[tex].body
    return decode_alpha(bytearray(raw[:NPIX])), decode_color(bytearray(raw[:NPIX]))


def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


def stat(name, byid, fz, m2t, pred):
    cores, edges, ncol = [], [], 0
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if not (c and len(c) == 1 and pred(ord(c))):
            continue
        a, g = chans(byid, m2t[e.mat])
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        A = a[y0:y1, x0:x1].astype(np.float32)
        G = g[y0:y1, x0:x1].astype(np.float32)
        solid = A > 200
        if solid.sum() < 5:
            continue
        # median color WHERE the glyph is solid = the "ink color"
        cores.append(float(np.median(G[solid])))
        ncol += 1
        if ncol >= 40:
            break
    if cores:
        print(f"{name:>18} n={len(cores):3d}  color-on-solid-ink median={np.median(cores):.0f} "
              f"(255=white, ~210=gray glow)  min={min(cores):.0f} max={max(cores):.0f}")
    else:
        print(f"{name}: none")


b_byid, b_fz, b_m2t = load(DPC + ".he_backup")
d_byid, d_fz, d_m2t = load(DPC)
print("The 'ink color' = median of the COLOR channel where alpha is solid.\n")
stat("ORIG arabic", b_byid, b_fz, b_m2t, is_ar)
stat("ORIG latin", b_byid, b_fz, b_m2t, lambda cp: 0x21 <= cp <= 0x7E)
stat("OUR hebrew", d_byid, d_fz, d_m2t, lambda cp: 0x05D0 <= cp <= 0x05EA)
stat("OUR latin", d_byid, d_fz, d_m2t, lambda cp: 0x21 <= cp <= 0x7E)
