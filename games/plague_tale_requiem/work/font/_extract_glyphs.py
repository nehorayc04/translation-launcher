# -*- coding: utf-8 -*-
"""Extract native Arabic (TARGET) and current Hebrew glyphs from the atlas as alpha PNGs,
so the skill's measure_font.py can compare weight/softness/size. Ground-truth calibration."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from build_hebrew_font import (DpcRepack, FontsZ, decode_alpha, resolve_mat_textures,
                               NPIX, SIDE, BIG, BACKUP)

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
OUT = os.path.dirname(os.path.abspath(__file__))
SCR = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
       r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
       r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")


def load(dpc):
    D = DpcRepack(dpc)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    pages = {}
    for tex in set(m2t.values()):
        pages[tex] = decode_alpha(bytearray(byid[tex].body[:NPIX]))
    return fz, m2t, pages


def crop(e, m2t, pages):
    tex = m2t.get(e.mat)
    if tex is None:
        return None
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    if x1 <= x0 or y1 <= y0:
        return None
    a = pages[tex][y0:y1, x0:x1]
    return a if a.size and a.max() > 20 else None


def dump(fz, m2t, pages, cids, tag, n):
    got = 0
    montage = []
    for e in sorted(fz.entries, key=lambda e: e.cid):
        if not cids(e.cid):
            continue
        a = crop(e, m2t, pages)
        if a is None:
            continue
        p = os.path.join(SCR, f"GLYPH_{tag}_{e.cid:04x}.png")
        Image.fromarray(a, "L").convert("LA").save(p)  # alpha via L->LA (value=alpha)
        # actually save as alpha: white where ink, alpha=value
        rgba = np.zeros((*a.shape, 4), np.uint8); rgba[..., :3] = 255; rgba[..., 3] = a
        Image.fromarray(rgba, "RGBA").save(p)
        montage.append(a)
        got += 1
        if got >= n:
            break
    # a combined strip for one measure call
    if montage:
        h = max(m.shape[0] for m in montage)
        strip = np.zeros((h, sum(m.shape[1] + 4 for m in montage)), np.uint8)
        x = 0
        for m in montage:
            strip[:m.shape[0], x:x + m.shape[1]] = m
            x += m.shape[1] + 4
        rgba = np.zeros((*strip.shape, 4), np.uint8); rgba[..., :3] = 255; rgba[..., 3] = strip
        pth = os.path.join(SCR, f"STRIP_{tag}.png")
        Image.fromarray(rgba, "RGBA").save(pth)
        print(f"{tag}: {got} glyphs -> {pth}")
    return got


def is_ar(cp):
    # cid = the char's UTF-8 bytes as an int. Arabic presentation forms U+FE80-FEFF -> UTF-8
    # EF BA/BB xx -> cid 0xEFBAxx / 0xEFBBxx ; 2-byte Arabic U+06xx -> D8/D9 xx.
    return (cp >> 8) in (0xEFBA, 0xEFBB, 0xD8, 0xD9)
def is_he(cp):
    return 0xD790 <= cp <= 0xD7AA


print("=== NATIVE ARABIC (pristine backup) ===")
fz, m2t, pages = load(DPC + BACKUP)
dump(fz, m2t, pages, is_ar, "AR", 12)

print("=== CURRENT HEBREW (deployed) ===")
fz2, m2t2, pages2 = load(DPC)
dump(fz2, m2t2, pages2, is_he, "HE", 12)
