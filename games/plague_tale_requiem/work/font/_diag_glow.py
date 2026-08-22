# -*- coding: utf-8 -*-
"""Measure the shipped font's COLOUR channel as a function of DISTANCE FROM THE INK.

The wide picture (BOX_original.png vs BOX_deployed.png) proved the shipped colour channel is a
soft GLOW that follows the glyph and fades to BLACK — NOT a flat floor, and NOT a rectangle.
My previous 'noise fix' wrote a hard 37-gray rectangle over the whole slot = the dark box the
user sees, with a hard edge = the 'noise around the box'.

Recover the real curve over the WHOLE page (every ink pixel belongs to some glyph, so distance
from the NEAREST ink is exactly the glow coordinate). Then fit
colour = PEAK * gaussian_blur(coverage, sigma) so it can be reproduced exactly.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageFilter
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, decode_color, resolve_mat_textures, NPIX, BIG

GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
MAXD = 18


def dist_from_ink(mask, maxd=MAXD):
    d = np.full(mask.shape, 99, np.int32)
    d[mask] = 0
    cur = mask.copy()
    for k in range(1, maxd + 1):
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]
        nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]
        nxt[:, :-1] |= cur[:, 1:]
        new = nxt & ~cur
        d[new] = k
        cur = nxt
    return d


def profile(path, label):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    tex = sorted(set(m2t.values()))[0]
    raw = byid[tex].body
    a = decode_alpha(bytearray(raw[:NPIX]))
    g = decode_color(bytearray(raw[:NPIX]))
    ink = a > 128
    d = dist_from_ink(ink)
    print(f"\n=== {label}  (page {tex:016X}, ink texels={int(ink.sum()):,}) ===")
    print(f"{'dist(px)':>8} {'colour':>8} {'sd':>6} {'texels':>9}")
    prof = []
    for k in range(0, MAXD + 1):
        sel = d == k
        if sel.sum() > 50:
            v = float(g[sel].mean())
            prof.append((k, v))
            print(f"{k:>8} {v:>8.1f} {float(g[sel].std()):>6.1f} {int(sel.sum()):>9,}")
    far = d == 99
    print(f"     far {float(g[far].mean()):>8.1f} {float(g[far].std()):>6.1f} {int(far.sum()):>9,}"
          f"   <- background far from any ink")
    return prof


prof = profile(GAME + ".he_backup", "ORIGINAL (shipped Asobo font)")
profile(GAME, "DEPLOYED (mine)")

print("\n=== fit: colour = PEAK * gaussian_blur(coverage, sigma) ===")
size = 140
im = Image.new("L", (size, size), 0)
im.paste(255, (50, 30, 90, 110))
base = np.array(im, np.uint8)
mask = base > 128
d = dist_from_ink(mask)
best = None
for sigma in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
    bl = np.array(Image.fromarray(base).filter(ImageFilter.GaussianBlur(sigma)), np.float32) / 255.0
    for peak in [150, 157, 165, 175, 185, 200]:
        cur = bl * peak
        err, cnt = 0.0, 0
        for k, want in prof:
            sel = d == k
            if sel.sum():
                err += (float(cur[sel].mean()) - want) ** 2
                cnt += 1
        err = (err / max(1, cnt)) ** 0.5
        if best is None or err < best[0]:
            best = (err, sigma, peak)
print(f"BEST: sigma={best[1]}  peak={best[2]}  rms_err={best[0]:.1f}")
bl = np.array(Image.fromarray(base).filter(ImageFilter.GaussianBlur(best[1])), np.float32) / 255.0 * best[2]
print(f"{'dist':>6} {'shipped':>8} {'fit':>8}")
for k, want in prof:
    sel = d == k
    if sel.sum():
        print(f"{k:>6} {want:>8.1f} {float(bl[sel].mean()):>8.1f}")
