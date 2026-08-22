# -*- coding: utf-8 -*-
"""What IS the title's last rendered glyph?  Correlate it against every atlas
glyph (scaled to the same ink height) and against a LEFT-TRUNCATED tav.
Never read Hebrew off a screenshot — this is the reliable instrument.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG

SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"


def glyph_inks():
    D = DpcRepack(r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache, out = {}, {}
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if c not in HEB or e.mat not in m2t:
            continue
        t = m2t[e.mat]
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        g = cache[t][int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        ys = np.where((g > 60).any(axis=1))[0]
        xs = np.where((g > 60).any(axis=0))[0]
        out[c] = g[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(float) / 255.0
    return out


def norm(a):
    a = np.asarray(a, float)
    a = a - a.min()
    m = a.max()
    return a / m if m else a


def score(A, B):
    Bi = np.asarray(Image.fromarray((np.clip(B, 0, 1) * 255).astype(np.uint8), "L")
                    .resize((A.shape[1], A.shape[0]), Image.BILINEAR), float) / 255.0
    return float(((norm(A) - norm(Bi)) ** 2).mean())


def cut(im, box, thr=45):
    a = 255 - np.asarray(im.crop(box), float)
    ys = np.where((a > thr).any(axis=1))[0]
    xs = np.where((a > thr).any(axis=0))[0]
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def report(im, box, label, inks, truth):
    sub = cut(im, box)
    print(f"\n--- {label}: rendered {sub.shape[1]}w x {sub.shape[0]}h "
          f"aspect {sub.shape[1]/sub.shape[0]:.3f} ---")
    res = [(score(sub, g), c) for c, g in inks.items()]
    t = inks[truth]
    for n in (2, 3, 4, 5, 6, 7, 8):
        if t.shape[1] - n > 4:
            res.append((score(sub, t[:, n:]), f"{truth}-cutL{n}"))
            res.append((score(sub, t[:, :-n]), f"{truth}-cutR{n}"))
    res.sort()
    for s, c in res[:6]:
        print(f"     {c:12} mse={s:.4f}")
    print(f"     [{truth} full aspect {t.shape[1]/t.shape[0]:.3f}]")


def main():
    inks = glyph_inks()
    im = Image.open(os.path.join(SC, "AUTOCHECK_weight.png")).convert("L")
    # title 'הגדרות' — blobs measured earlier at crop(150) x: 18-36,40-45,49-66,70-90,94-108,111-132
    report(im, (166, 108, 188, 168), "TITLE last glyph (should be tav)", inks, "ת")
    report(im, (259, 108, 285, 168), "TITLE first glyph (should be he)", inks, "ה")
    report(im, (198, 108, 218, 168), "TITLE 3rd-from-left (should be resh)", inks, "ר")


main()
