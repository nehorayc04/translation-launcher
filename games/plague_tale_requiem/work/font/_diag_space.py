# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, NPIX
sys.path.insert(0, "..")
import pt_text

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")

D = DpcRepack(DPC)
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
m2t = resolve_mat_textures(byid, fz)


def page(tex):
    return decode_alpha(bytearray(byid[tex].body[:NPIX]))


# every entry whose char is SPACE or a control/format char (what a subtitle might contain)
print("=== space + control/format glyphs in BIG_ARABIC ===")
for e in fz.entries:
    c = cid_to_char(e.cid)
    if not c:
        continue
    cp = ord(c[0])
    if cp == 0x20 or cp < 0x20 or cp in (0xA0, 0x200C, 0x200D, 0x200E, 0x200F, 0x2028, 0x2029):
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        yy0, yy1 = min(y0, y1), max(y0, y1)
        xx0, xx1 = min(x0, x1), max(x0, x1)
        a = page(m2t[e.mat])[yy0:yy1, xx0:xx1]
        fill = (a > 128).mean() if a.size else 0
        amax = int(a.max()) if a.size else 0
        print(f"  cp=U+{cp:04X} box=({x0},{y0},{x1},{y1}) sizeWxH={x1-x0}x{y1-y0} "
              f"adv={e.adv:.0f} bx={e.bx:.0f} fill={fill:.2f} amax={amax}")
        if a.size and (xx1-xx0)*(yy1-yy0) > 30:
            Image.fromarray(page(m2t[e.mat])[yy0:yy1, xx0:xx1], "L").save(
                os.path.join(SC, f"glyph_U{cp:04X}.png"))

# what characters does the ACTUAL deployed Hebrew subtitle line contain?
print("\n=== actual stored Hebrew subtitle chars ===")
ar = pt_text.load_map(pt_text.lang_path(pt_text.SLOT_ID))
hits = [(k, v) for k, v in ar.items() if "לתפוס אותנו" in v or "מאחורינו" in v]
for k, v in hits[:3]:
    cps = sorted({f"U+{ord(ch):04X}" for ch in v if ord(ch) < 0x20 or ord(ch) == 0x7C or ord(ch) == 0x640})
    print(f"  {k}: control/pipe/tatweel chars present = {cps or 'NONE'}")
    print(f"     value={v!r}")
