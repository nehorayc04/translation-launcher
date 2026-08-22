# -*- coding: utf-8 -*-
"""Enumerate ALL Fonts_Z objects + measure their Latin letter ink-heights, to find the
LATIN SUBTITLE font (what English renders with) and its size = the target for Hebrew."""
import sys, struct
sys.path.insert(0, ".")
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, TEX_CLASS, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"

D = DpcRepack(DPC + ".he_backup")   # ORIGINAL: untouched Latin fonts
allobj = list(D.db_objs) + [o for _, o, _ in D.fb_objs]
byid = {o.oid: o for o in allobj}
texids = {o.oid for o in allobj if o.otype == TEX_CLASS}


def resolve(fz):
    mats = list(struct.unpack_from("<10Q", fz.tail, 4)) if len(fz.tail) >= 84 else []
    m2t = {}
    for i, mid in enumerate(mats):
        if mid not in byid:
            continue
        b = byid[mid].info + byid[mid].body
        for off in range(0, len(b) - 8):
            if struct.unpack_from("<Q", b, off)[0] in texids:
                m2t[i] = struct.unpack_from("<Q", b, off)[0]; break
    return m2t


for o in allobj:
    try:
        fz = FontsZ(o.body)
    except Exception:
        continue
    if not (1 < fz.count < 2000):
        continue
    # does it parse cleanly? sample entries must have plausible boxes
    lat = [e for e in fz.entries if (lambda c: c and len(c) == 1 and 0x41 <= ord(c) <= 0x7A)(cid_to_char(e.cid))]
    ara = [e for e in fz.entries if (lambda c: c and (0x0600 <= ord(c[0]) <= 0x06FF or 0xFB50 <= ord(c[0]) <= 0xFEFF))(cid_to_char(e.cid))]
    if len(lat) < 5:
        continue
    m2t = resolve(fz)
    if not m2t:
        print(f"obj {o.oid:016X}: count={fz.count} latin={len(lat)} arabic={len(ara)} (no textures resolved)")
        continue
    heights = []
    for e in lat[:60]:
        if e.mat not in m2t:
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        if x1 <= x0 or y1 <= y0:
            continue
        a = decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))[y0:y1, x0:x1]
        ys, _ = np.where(a > 100)
        if len(ys):
            heights.append(ys.max() - ys.min() + 1)
    h = np.array(heights) if heights else np.array([0])
    # cap height from 'H' specifically
    capH = None
    for e in lat:
        if cid_to_char(e.cid) == "H" and e.mat in m2t:
            x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
            a = decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))[y0:y1, x0:x1]
            ys, _ = np.where(a > 100)
            if len(ys): capH = ys.max() - ys.min() + 1
            break
    print(f"obj {o.oid:016X}: count={fz.count:4d} latin={len(lat):3d} arabic={len(ara):3d}  "
          f"latin ink median={np.median(h):.0f} p25={np.percentile(h,25):.0f} "
          f"p75={np.percentile(h,75):.0f}  capH('H')={capH}")
