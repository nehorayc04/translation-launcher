# -*- coding: utf-8 -*-
"""Measure ONLY the last (leftmost) glyph of several real in-game Hebrew lines.

If every line loses roughly the SAME number of pixels off its final glyph, the
cause is our own metrics / the engine's line-end, not a container clip (a
container clip would scale with how far the line overflows, and short lines
would not clip at all).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG

GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"


def atlas():
    D = DpcRepack(GAME)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, info = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        g = cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        ys = np.where((g > 90).any(axis=1))[0]
        xs = np.where((g > 90).any(axis=0))[0]
        info[c] = dict(inkw=int(xs.max() - xs.min() + 1), inkh=int(ys.max() - ys.min() + 1),
                       boxw=float(e.x1 - e.x0), bx=float(e.bx))
    return info


ORD_INK = 31.0        # atlas ink height of an ordinary Hebrew letter (uniform build)


def lastglyph(shot, box, last_char, label, info, thr=110):
    a = 255 - np.asarray(Image.open(shot).crop(box).convert("L"), dtype=np.int16)
    ink = a > thr
    cols = ink.any(axis=0)
    if not cols.any():
        print(f"  {label:<22} no ink"); return None
    sp, s = [], None
    for i, v in enumerate(cols):
        if v and s is None:
            s = i
        elif not v and s is not None:
            sp.append([s, i]); s = None
    if s is not None:
        sp.append([s, len(cols)])
    m = []
    for a0, a1 in sp:
        if m and a0 - m[-1][1] <= 2:
            m[-1][1] = a1
        else:
            m.append([a0, a1])
    s0, s1 = m[0]                                   # leftmost blob = LAST char (RTL)
    sub = a[:, s0:s1]
    ys = np.where((sub > thr).any(axis=1))[0]
    # line scale from the whole line's ORDINARY ink height
    rows = np.where(ink.any(axis=1))[0]
    lh = rows.max() - rows.min() + 1
    scale = lh / ORD_INK
    exp = info[last_char]["inkw"] * scale
    w = s1 - s0
    print(f"  {label:<22} last '{last_char}'  line_h={lh:2d} scale={scale:.3f}  "
          f"rendered {w:3d}px  expected {exp:5.1f}px  delta {w-exp:+5.1f}"
          f"   leftedge_abs_x={box[0]+s0}")
    return w - exp


def main():
    info = atlas()
    shot = os.path.join(SC, "AUTOCHECK_weight.png")
    print("\n--- last-glyph width, several independent lines ---")
    ds = []
    for box, ch, lab in [
        ((150, 105, 300, 170), "ת", "TITLE hgdrot"),
        ((1240, 178, 1372, 232), "ת", "TAB bakarot"),
        ((1060, 178, 1180, 232), "ע", "TAB shema"),
        ((330, 272, 500, 312), "י", "row1 ramat-kushi"),
        ((330, 342, 500, 384), "ע", "row2 tdirut"),
        ((330, 412, 500, 454), "ה", "row3 reida"),
        ((330, 766, 500, 808), "ת", "row8 matarot"),
        ((330, 696, 500, 738), "ך", "row7 madrich"),
    ]:
        d = lastglyph(shot, box, ch, lab, info)
        if d is not None:
            ds.append(d)
    if ds:
        print(f"\n  median delta = {np.median(ds):+.2f}px   all = {[round(x,1) for x in ds]}")


main()
