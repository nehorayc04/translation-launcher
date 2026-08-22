# -*- coding: utf-8 -*-
"""Is the LAST letter of a Hebrew line CLIPPED in-game?

Never read Hebrew off a screenshot. Instead: we KNOW the string (from the spine),
so map blob i -> character deterministically (RTL: blob 0 = last char), fit the
screen scale from the letters that are NOT at either end, and then check whether
the end letters render at their expected width.
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
                       boxw=float(e.x1 - e.x0), boxh=float(e.y1 - e.y0), bx=float(e.bx),
                       adv=float(e.x1 - e.x0) + float(e.bx),
                       gapL=int(xs.min()), gapR=int(g.shape[1] - 1 - xs.max()))
    return info


def line(shot, box, text, label, info, thr=110):
    x0, y0, x1, y1 = box
    a = 255 - np.asarray(Image.open(shot).crop(box).convert("L"), dtype=np.int16)
    ink = a > thr
    cols = ink.any(axis=0)
    sp, s = [], None
    for i, v in enumerate(cols):
        if v and s is None:
            s = i
        elif not v and s is not None:
            sp.append([s, i]); s = None
    if s is not None:
        sp.append([s, len(cols)])
    # a detached leg (he/qof/…) is <=2px from its own letter — merge
    m = []
    for sp0, sp1 in sp:
        if m and sp0 - m[-1][1] <= 2:
            m[-1][1] = sp1
        else:
            m.append([sp0, sp1])
    letters = [c for c in text if c != " "]
    order = list(reversed(letters))          # RTL: blob 0 (leftmost) = LAST char
    print(f"\n=== {label}  '{text}'  blobs={len(m)} chars={len(letters)} ===")
    if len(m) != len(letters):
        print("    !! blob count != char count — spacing/merge ambiguous, skipping")
        return
    # fit scale on the MIDDLE letters only (ends are the suspects)
    mids = [(i, order[i]) for i in range(1, len(order) - 1)]
    ratios = [(m[i][1] - m[i][0]) / info[c]["inkw"] for i, c in mids if c in info]
    scale = float(np.median(ratios))
    print(f"    fitted scale (middle letters, n={len(ratios)}) = {scale:.4f}"
          f"   spread {min(ratios):.3f}..{max(ratios):.3f}")
    for i, c in enumerate(order):
        w = m[i][1] - m[i][0]
        exp = info[c]["inkw"] * scale
        d = w - exp
        tag = ""
        if i == 0:
            tag = "  <== LINE END (leftmost)"
        if i == len(order) - 1:
            tag = "  <== LINE START (rightmost)"
        flag = "   *** MISSING %.1fpx ***" % (-d) if d < -1.2 else ""
        print(f"    #{i:2d} '{c}'  rendered {w:3d}px  expected {exp:5.1f}px  "
              f"delta {d:+5.1f}{flag}{tag}")


def main():
    info = atlas()
    shot = os.path.join(SC, "AUTOCHECK_weight.png")
    print("atlas ink widths:", {c: info[c]["inkw"] for c in "הגדרותבקמט"})
    line(shot, (150, 105, 300, 170), "הגדרות", "TITLE", info)
    line(shot, (360, 765, 470, 810), "מטרות", "LEFT-COL", info)
    line(shot, (1255, 185, 1360, 225), "בקרות", "TAB", info)


main()
