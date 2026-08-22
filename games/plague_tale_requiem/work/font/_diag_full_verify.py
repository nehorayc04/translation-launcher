# -*- coding: utf-8 -*-
"""Pixel-verify the LATEST real user screenshot against the atlas, per row.

Never trust my own reading of the image — measure. For each settings row we
KNOW the string (extracted from tt23.pc), so map blob->char deterministically
(RTL: blob 0 = leftmost = LAST char) and compare rendered vs expected ink width.
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG

SHOTS = r"C:\Users\Nehoray_Cohen\Pictures\Screenshots"
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
THR = 100


def latest_shot():
    files = sorted(glob.glob(os.path.join(SHOTS, "*.png")), key=os.path.getmtime)
    return files[-1]


def atlas():
    D = DpcRepack(r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
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
        ys = np.where((g > THR).any(axis=1))[0]
        xs = np.where((g > THR).any(axis=0))[0]
        info[c] = int(xs.max() - xs.min() + 1)
    return info


def row(im, box, text, info, invert=True):
    a = np.asarray(im.crop(box).convert("L"), float)
    a = (255 - a) if invert else a
    ink = a > THR
    cols = ink.any(axis=0)
    sp, s = [], None
    for i, v in enumerate(cols):
        if v and s is None:
            s = i
        elif not v and s is not None:
            sp.append([s, i]); s = None
    if s is not None:
        sp.append([s, len(cols)])
    m = []
    for x0, x1 in sp:
        if m and x0 - m[-1][1] <= 2:
            m[-1][1] = x1
        else:
            m.append([x0, x1])
    letters = [c for c in text if c != " "]
    rowh = ink.any(axis=1)
    ys = np.where(rowh)[0]
    lh = (ys.max() - ys.min() + 1) if len(ys) else 0
    print(f"\n{text!r:26} box={box}  blobs={len(m)} chars={len(letters)} line_h={lh}")
    if len(m) != len(letters):
        print("   MISMATCH — widths:", [(b[0], b[1] - b[0]) for b in m])
        return None
    order = list(reversed(letters))
    r = [(m[i][1] - m[i][0]) / info[c] for i, c in enumerate(order) if 0 < i < len(order) - 1]
    if not r:
        return None
    scale = float(np.median(r))
    end = order[0]
    w = m[0][1] - m[0][0]
    exp = info[end] * scale
    d = w - exp
    flag = "  *** SHORT — CLIPPED ***" if d < -1.5 else "  OK"
    print(f"   scale={scale:.3f}  LAST char '{end}': rendered {w} expected {exp:.1f} delta {d:+.1f}{flag}")
    return d


def main():
    shot = latest_shot()
    print("latest screenshot:", shot, " mtime", os.path.getmtime(shot))
    im = Image.open(shot)
    print("size", im.size)
    info = atlas()
    W, H = im.size
    sx, sy = W / 1600.0, H / 900.0

    def box(x0, y0, x1, y1):
        return (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))

    rows = [
        (box(160, 105, 300, 170), "הגדרות"),
        (box(330, 272, 500, 312), "החלפת ג'ויסטיק"),
        (box(330, 342, 500, 384), "הפוך ציר אופקי של מצלמה"),
        (box(330, 412, 500, 454), "הפוך את ציר המצלמה האנכי"),
        (box(330, 482, 500, 524), "רגישות המצלמה"),
        (box(330, 552, 500, 594), "רגישות כוונון"),
        (box(330, 622, 500, 664), "רגישות תנועה"),
        (box(330, 692, 500, 734), "השתמש בסיוע כיוון"),
        (box(330, 750, 500, 830), "ביצוע אוטומטי של קלטים בזמן מוגדר"),
        (box(950, 275, 1400, 310), "החלפת ג'ויסטיק"),
    ]
    ds = []
    for b, t in rows:
        d = row(im, b, t, info)
        if d is not None:
            ds.append(d)
    if ds:
        print(f"\nend-of-line deltas: {[round(x,1) for x in ds]}   median={np.median(ds):+.2f}")


main()
