# -*- coding: utf-8 -*-
"""Read the DEPLOYED font back out of the game folder and assert the six properties that
matter. Never trust the builder's own report — this re-parses the file the game will load."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX, BIG, REQ_PX, _HE_TALL, _HE_SHORT

GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"


def load(p):
    D = DpcRepack(p)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    cache = {}

    def pg(t):
        if t not in cache:
            cache[t] = decode_alpha(bytearray(byid[t].body[:NPIX]))
        return cache[t]
    return fz, m2t, pg


fz, m2t, pg = load(GAME)
rows, fails = [], []
for e in fz.entries:
    c = cid_to_char(e.cid)
    if c not in HEB or e.mat not in m2t:
        continue
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    a = pg(m2t[e.mat])
    box = a[y0:y1, x0:x1]
    ys, xs = np.where(box > 60)
    if not len(ys):
        fails.append(f"{c}: EMPTY box"); continue
    ih = int(ys.max() - ys.min() + 1)
    # clipping: only VERTICAL matters — the box WIDTH is deliberately tight (= glyph width,
    # so the advance is correct), exactly like the vanilla fonts, so ink touching the left/right
    # edge is by design and not a defect.
    clip = (ys.min() == 0) or (ys.max() == box.shape[0] - 1)
    # leftovers / neighbour bleed: any ink in a 10px halo OUTSIDE the declared box
    hy0, hy1 = max(0, y0 - 10), min(512, y1 + 10)
    hx0, hx1 = max(0, x0 - 10), min(512, x1 + 10)
    halo = a[hy0:hy1, hx0:hx1].astype(np.int32).copy()
    halo[y0 - hy0:y1 - hy0, x0 - hx0:x1 - hx0] = 0
    rows.append(dict(ch=c, bw=x1 - x0, bh=y1 - y0, ih=ih, adv=e.adv, bx=e.bx,
                     clip=clip, halo=int((halo > 60).sum())))

bh = sorted({r["bh"] for r in rows})
adv = sorted({round(r["adv"], 2) for r in rows})
std = [r["ih"] for r in rows if r["ch"] not in _HE_TALL + _HE_SHORT + "ךןףץק"]
body = int(np.median(std)) if std else 0
print(f"glyphs           : {len(rows)}/27")
print(f"box heights      : {bh}                {'UNIFORM OK' if len(bh) == 1 else 'NOT UNIFORM'}")
print(f"adv values       : {adv}              {'IDENTICAL OK' if len(adv) == 1 else 'VARIES'}")
print(f"leftover/bleed   : {sum(r['halo'] for r in rows)} px            "
      f"{'CLEAN OK' if sum(r['halo'] for r in rows) == 0 else 'DIRTY <-- the dots'}")
print(f"clipped glyphs   : {sum(r['clip'] for r in rows)}                 "
      f"{'OK' if not any(r['clip'] for r in rows) else 'CLIPPED'}")
print(f"body(ordinary)   : {body}px   box {bh[0] if bh else 0}px   ratio {body / bh[0]:.3f}"
      f"   -> predicted screen body {REQ_PX * body / bh[0]:.1f}px")
for k in ("ל", "נ", "מ", "י", "ק", "ן"):
    r = next((r for r in rows if r["ch"] == k), None)
    if r:
        print(f"   {k}: ink {r['ih']:>3}px  box {r['bw']}x{r['bh']}  "
              f"-> screen {REQ_PX * r['ih'] / r['bh']:.1f}px")
for f in fails:
    print("FAIL", f)
