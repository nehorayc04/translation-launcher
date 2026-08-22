# -*- coding: utf-8 -*-
"""Compare the ORIGINAL Asobo glyph coverage profile vs OUR injected glyphs.
The original is what the user is fine with; match its aa_frac + edge to kill the
'outline merges into a background' look."""
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageFilter
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, SIDE

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358


def load(path):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    return byid, fz, resolve_mat_textures(byid, fz)


def alpha_page(byid, tex):
    return decode_alpha(bytearray(byid[tex].body[:NPIX]))


def profile(a, e):
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    box = a[y0:y1, x0:x1]
    if box.size == 0:
        return None
    solid = int((box > 200).sum())
    mid = int(((box > 20) & (box <= 200)).sum())
    faint = int(((box > 0) & (box <= 20)).sum())
    aa = mid / max(1, solid)
    # outline ring at a LOW coverage threshold (what a readability-outline shader uses)
    cov = (box > 12).astype(np.uint8) * 255
    dil = np.array(Image.fromarray(cov).filter(ImageFilter.MaxFilter(5)))
    ring = int(((dil > 0) & (cov == 0)).sum())
    fill = solid / max(1, box.size)
    return dict(solid=solid, mid=mid, faint=faint, aa=aa, ring=ring, fill=fill,
                w=x1 - x0, h=y1 - y0)


def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


# ORIGINAL: sample real Arabic glyphs from the backup (what the game shipped)
b_byid, b_fz, b_m2t = load(DPC + ".he_backup")
orig = []
for e in b_fz.entries:
    c = cid_to_char(e.cid)
    if c and len(c) == 1 and is_ar(ord(c)):
        p = profile(alpha_page(b_byid, b_m2t[e.mat]), e)
        if p:
            orig.append(p)

# OURS: Hebrew + repacked Latin in the deployed font
d_byid, d_fz, d_m2t = load(DPC)
heb, lat = [], []
for e in d_fz.entries:
    c = cid_to_char(e.cid)
    if not c or len(c) != 1:
        continue
    if 0x05D0 <= ord(c) <= 0x05EA:
        p = profile(alpha_page(d_byid, d_m2t[e.mat]), e)
        if p: heb.append(p)
    elif 0x21 <= ord(c) <= 0x7E:
        p = profile(alpha_page(d_byid, d_m2t[e.mat]), e)
        if p: lat.append(p)


def summ(name, lst):
    if not lst:
        print(f"{name}: none"); return
    aa = np.array([x["aa"] for x in lst])
    fill = np.array([x["fill"] for x in lst])
    faint = np.array([x["faint"] for x in lst])
    ring = np.array([x["ring"] for x in lst])
    print(f"{name:>18} n={len(lst):3d}  aa median={np.median(aa):.2f} "
          f"mean={aa.mean():.2f}  fill median={np.median(fill):.2f}  "
          f"faint median={np.median(faint):.0f}  ring median={np.median(ring):.0f}")


print("aa = mid-tone/solid (edge softness);  fill = solid/box;  "
      "faint = 1..20 alpha px;  ring = outline dilation px\n")
summ("ORIGINAL arabic", orig)
summ("OUR hebrew", heb)
summ("OUR latin/digit", lat)
