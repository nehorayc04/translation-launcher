# -*- coding: utf-8 -*-
"""Find BIG_ARABIC glyphs whose atlas box is a FILLED / dark plate (a background).
English uses a separate Latin font (no band); Hebrew rides BIG_ARABIC. If the Arabic
SPACE (or a joiner/baseline glyph) is a solid dark rectangle, every space draws a black
box -> the band behind Hebrew subtitles."""
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char, cid_to_char as c2c
from build_hebrew_font import decode_alpha, decode_color, resolve_mat_textures, NPIX

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")

# check BOTH the deployed font and the ORIGINAL backup (the band may be a shipped Arabic glyph)
for tag, path in (("DEPLOYED", DPC), ("ORIGINAL", DPC + ".he_backup")):
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fz = FontsZ(byid[BIG].body)
    m2t = resolve_mat_textures(byid, fz)
    pages = {}
    def page(tex):
        if tex not in pages:
            pages[tex] = decode_alpha(bytearray(byid[tex].body[:NPIX]))
        return pages[tex]

    print(f"\n===== {tag} =====")
    # the whitespace / low codepoints Hebrew text actually uses: space, and any glyph
    # with a big box that is mostly FILLED (alpha high across the whole box = a plate)
    filled = []
    for e in fz.entries:
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        w, h = x1 - x0, y1 - y0
        if w < 3 or h < 3:
            continue
        a = page(m2t[e.mat])[y0:y1, x0:x1]
        fill = (a > 128).mean()
        c = cid_to_char(e.cid)
        cp = ord(c[0]) if c else None
        if fill > 0.6 and w * h > 200:            # box mostly ink = a plate
            filled.append((fill, w, h, cp, c, e))
    filled.sort(reverse=True)
    print(f"  glyphs with >60% filled box (candidate background plates): {len(filled)}")
    for fill, w, h, cp, c, e in filled[:15]:
        cps = f"U+{cp:04X}" if cp else "None"
        print(f"    fill={fill:.2f} {w}x{h} cp={cps} char={c!r} box=({int(e.x0)},{int(e.y0)})")

    # explicitly show the SPACE glyph (0x20) and a few likely whitespace/joiner cids
    print("  whitespace/low glyphs:")
    for target in (0x20, 0xA0, 0x200C, 0x200D, 0x061C, 0xFEFF):
        for e in fz.entries:
            c = cid_to_char(e.cid)
            if c and ord(c[0]) == target:
                x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
                a = page(m2t[e.mat])[y0:y1, x0:x1]
                fill = (a > 128).mean() if a.size else 0
                print(f"    U+{target:04X} box {x1-x0}x{y1-y0} fill={fill:.2f} amax={int(a.max()) if a.size else 0}")
                if tag == "DEPLOYED" and a.size and (x1-x0)*(y1-y0) > 50:
                    Image.fromarray(page(m2t[e.mat])[y0:y1, x0:x1], "L").save(
                        os.path.join(SC, f"ws_{target:04X}.png"))
                break
