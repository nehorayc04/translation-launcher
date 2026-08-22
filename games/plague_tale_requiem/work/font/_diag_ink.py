# -*- coding: utf-8 -*-
"""Find noise INSIDE the glyph. Compare, for ORIGINAL Arabic glyphs vs OUR Hebrew glyphs:
  * the COLOUR channel where alpha is ink / edge / background
  * per-4x4-block variation of the colour endpoints (BC1 blockiness = visible noise)
  * the alpha edge profile
If the shipped font keeps the colour FLAT even where alpha=0, then our 'colour only under the
glyph' fill creates a hard 155<->0 step inside every edge block -> BC1 quantises it to 4 levels
-> blocky speckle along every stroke = the reported noise."""
import sys
sys.path.insert(0, ".")
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, decode_color, resolve_mat_textures, NPIX, BIG

GAME = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"


def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


def analyse(path, label, pick):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    pages = {}
    def pg(t):
        if t not in pages:
            raw = byid[t].body
            pages[t] = (decode_alpha(bytearray(raw[:NPIX])), decode_color(bytearray(raw[:NPIX])))
        return pages[t]
    rows = []
    for e in fz.entries:
        c = cid_to_char(e.cid)
        if not (c and len(c) == 1 and pick(ord(c))):
            continue
        if e.mat not in m2t:
            continue
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        a, g = pg(m2t[e.mat])
        A = a[y0:y1, x0:x1].astype(np.int32)
        G = g[y0:y1, x0:x1].astype(np.int32)
        ink = A >= 200
        bg = A <= 20
        edge = (A > 20) & (A < 200)
        if ink.sum() < 20 or bg.sum() < 20:
            continue
        rows.append((c, G[ink].mean(), G[ink].std(), G[bg].mean(), G[bg].std(),
                     G[edge].mean() if edge.sum() else 0, edge.sum() / max(1, ink.sum())))
        if len(rows) >= 12:
            break
    print(f"\n=== {label} ===")
    print(f"{'ch':>3} {'colour@ink':>12} {'sd':>6} {'colour@bg':>11} {'sd':>6} {'colour@edge':>12} {'edge/ink':>9}")
    for c, im, isd, bm, bsd, em, er in rows:
        print(f"{c:>3} {im:>12.1f} {isd:>6.1f} {bm:>11.1f} {bsd:>6.1f} {em:>12.1f} {er:>9.2f}")
    if rows:
        print(f"  MEAN colour: ink={np.mean([r[1] for r in rows]):.1f}  "
              f"background={np.mean([r[3] for r in rows]):.1f}  edge={np.mean([r[5] for r in rows]):.1f}")
        print(f"  -> colour step ink->bg = {np.mean([r[1] for r in rows]) - np.mean([r[3] for r in rows]):.1f} "
              f"(a BIG step inside edge blocks = BC1 blockiness = NOISE)")


analyse(GAME + ".he_backup", "ORIGINAL Arabic glyphs (the shipped font)", is_ar)
analyse(GAME, "OUR Hebrew glyphs (deployed)", lambda cp: 0x05D0 <= cp <= 0x05EA)
