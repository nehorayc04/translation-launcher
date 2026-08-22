# -*- coding: utf-8 -*-
import sys, struct
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ
from build_hebrew_font import decode_alpha, NPIX
SC = r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad"
DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
D = DpcRepack(DPC + ".he_backup")   # PRISTINE original
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
mc = struct.unpack_from("<I", fz.tail, 0)[0]
mats = list(struct.unpack_from("<%dQ" % mc, fz.tail, 4))
texids = {o.oid for o in byid.values() if o.otype == 0xE9659CD1C3F3326D}


def mat2tex(mi):
    b = byid[mats[mi]].info + byid[mats[mi]].body
    for off in range(len(b) - 8):
        v = struct.unpack_from("<Q", b, off)[0]
        if v in texids:
            return v


def decode_bc1(data, W=512, H=512):
    out = np.zeros((H, W), np.uint8); bpr = W // 4
    for by in range(H // 4):
        for bx in range(bpr):
            o = (by * bpr + bx) * 16 + 8
            c0 = struct.unpack_from("<H", data, o)[0]; c1 = struct.unpack_from("<H", data, o + 2)[0]
            bits = int.from_bytes(data[o + 4:o + 8], "little")
            g0 = ((c0 >> 11) & 31) * 255 // 31; g1 = ((c1 >> 11) & 31) * 255 // 31
            pal = [g0, g1, (2 * g0 + g1) // 3, (g0 + 2 * g1) // 3] if c0 > c1 else [g0, g1, (g0 + g1) // 2, 0]
            for i in range(16):
                out[by * 4 + i // 4, bx * 4 + i % 4] = pal[(bits >> (2 * i)) & 3]
    return out


for ch in ["A"]:
    e = fz.by_char(ch)
    tex = mat2tex(e.mat); raw = byid[tex].body
    al = decode_alpha(bytearray(raw[:NPIX])); co = decode_bc1(bytearray(raw[:NPIX]))
    x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
    A = al[y0:y1, x0:x1]; C = co[y0:y1, x0:x1]
    mid = ((A > 30) & (A < 225)).sum(); solid = (A >= 225).sum(); empty = (A <= 30).sum()
    print(f"'{ch}' box {x1-x0}x{y1-y0}  alpha: solid={solid} mid(31-224)={mid} empty={empty}  mid/solid={mid/max(1,solid):.2f}")
    row = A[A.shape[0] // 2]
    runs = []; c = 0
    for v in row:
        if v >= 180: c += 1
        elif c: runs.append(c); c = 0
    if c: runs.append(c)
    print(f"   mid-row stroke widths px: {sorted(runs, reverse=True)[:6]}")
    print(f"   color ink(alpha>200) mean={C[A>200].mean():.0f} range={C[A>200].min()}-{C[A>200].max()}  bg mean={C[A<30].mean():.0f}")
    af = A.astype(float) / 255; cf = C.astype(float) / 255
    print(f"   corr(color,alpha)={np.corrcoef(af.ravel(), cf.ravel())[0,1]:.2f}")
    Image.fromarray(A, "L").resize(((x1 - x0) * 6, (y1 - y0) * 6), Image.NEAREST).save(f"{SC}/orig_A_alpha.png")
    Image.fromarray(C, "L").resize(((x1 - x0) * 6, (y1 - y0) * 6), Image.NEAREST).save(f"{SC}/orig_A_color.png")
print("saved orig_A_alpha/color.png")
