# -*- coding: utf-8 -*-
"""Decode the DEPLOYED atlas and hunt the real noise source: stray ink AROUND each Hebrew
glyph (leftover Arabic from an incompletely-cleared box, or neighbour bleed from per-4x4-block
re-encoding). Saves a magnified sheet with a red frame at each glyph's DECLARED box so any
stray pixel outside the letter is obvious."""
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, decode_color, resolve_mat_textures, NPIX, gpu_rgba, BIG, SC

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
D = DpcRepack(DPC)                         # the DEPLOYED file (not the backup)
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
m2t = resolve_mat_textures(byid, fz)
heb = sorted([e for e in fz.entries if 0xD790 <= e.cid <= 0xD7AA], key=lambda e: e.cid)
print(f"{len(heb)} Hebrew glyphs in deployed font")

pages = {}
def page(tex):
    if tex not in pages:
        pages[tex] = gpu_rgba(bytearray(byid[tex].body[:NPIX]))
    return pages[tex]

M = 10                                      # margin (px) to inspect around the declared box
sheet = Image.new("RGB", (len(heb) * 80, 130), (30, 30, 30))
worst = []
for i, e in enumerate(heb):
    px = page(m2t[e.mat])
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    a = px[..., 3]
    # ink INSIDE the declared box
    inside = a[y0:y1, x0:x1]
    # ink in the MARGIN ring just OUTSIDE the declared box (this is stray = noise)
    ry0, ry1, rx0, rx1 = max(0, y0 - M), min(512, y1 + M), max(0, x0 - M), min(512, x1 + M)
    ring = a[ry0:ry1, rx0:rx1].copy().astype(np.int32)
    ring[y0 - ry0:y1 - ry0, x0 - rx0:x1 - rx0] = 0   # zero out the declared box -> only the ring remains
    stray = int((ring > 40).sum())
    strong = int((ring > 150).sum())
    worst.append((cid_to_char(e.cid), stray, strong))
    # magnified crop of box+margin, with a marker
    crop = px[ry0:ry1, rx0:rx1, :3]
    im = Image.fromarray(crop, "RGB").resize(((rx1 - rx0) * 1, (ry1 - ry0) * 1), Image.NEAREST)
    sheet.paste(im, (i * 80 + 4, 4))

worst.sort(key=lambda t: -t[1])
print("\nstray ink in the 10px ring OUTSIDE each glyph's box (should be ~0):")
for ch, stray, strong in worst:
    flag = "  <-- STRAY" if stray > 30 else ""
    print(f"  '{ch}': stray_px={stray:4d} strong_px={strong:4d}{flag}")
tot_stray = sum(t[1] for t in worst)
tot_strong = sum(t[2] for t in worst)
print(f"\nTOTAL stray={tot_stray} strong-stray={tot_strong}  (strong-stray>0 = visible leftover ink = NOISE)")
out = os.path.join(SC, "NOISE_rings.png")
sheet.save(out)
print("sheet:", out)
