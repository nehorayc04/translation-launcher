# -*- coding: utf-8 -*-
"""Learn the adv/box vertical semantics from ORIGINAL Arabic glyphs so we can set a
LARGER declared box (lower fill ratio -> smaller on-screen) while keeping the baseline."""
import sys
sys.path.insert(0, ".")
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358


def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
m2t = resolve_mat_textures(byid, fz)

print(f"{'ch':>3} {'adv':>6} {'y0':>4} {'y1':>4} {'boxH':>5} {'inkTop':>6} {'inkBot':>6} "
      f"{'ink_h':>5} {'fill':>5} {'adv-y0':>6} {'y1-inkBot':>9}")
rows = []
for e in fz.entries:
    c = cid_to_char(e.cid)
    if not (c and len(c) == 1 and is_ar(ord(c))):
        continue
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    if x1 <= x0 or y1 <= y0:
        continue
    a = decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))[y0:y1, x0:x1]
    ys, _ = np.where(a > 100)
    if len(ys) < 3:
        continue
    it, ib = y0 + ys.min(), y0 + ys.max()       # ink top/bottom in page coords
    ink_h = ib - it + 1
    boxH = y1 - y0
    rows.append((c, e.adv, y0, y1, boxH, it, ib, ink_h, ink_h / boxH,
                 e.adv - y0, y1 - ib))

# show a representative sample + aggregate the invariants
for r in rows[:14]:
    c, adv, y0, y1, boxH, it, ib, ink_h, fill, advy0, y1ib = r
    print(f"{c:>3} {adv:>6.0f} {y0:>4} {y1:>4} {boxH:>5} {it:>6} {ib:>6} {ink_h:>5} "
          f"{fill:>5.2f} {advy0:>6.0f} {y1ib:>9}")
adv_y0 = np.array([r[9] for r in rows])
fills = np.array([r[8] for r in rows])
print(f"\nn={len(rows)}  fill(ink/box) median={np.median(fills):.2f} p25={np.percentile(fills,25):.2f} "
      f"p75={np.percentile(fills,75):.2f}")
print(f"adv - y0: median={np.median(adv_y0):.1f}  (is adv == box top y0?  "
      f"{'YES' if abs(np.median(adv_y0))<2 else 'no, offset='+str(np.median(adv_y0))})")
