# -*- coding: utf-8 -*-
import sys, os, struct
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from inject_atlas import decode_alpha
SC = r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad"
DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
TEX1 = 0xEFC73FAE0445DAB6
D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
body = byid[TEX1].body
blocks = bytearray(body[4:])

def decode_bc1_color(data, W=512, H=512):
    """Decode the BC1 color part (bytes o+8..o+16) of each DXT5 block -> grayscale (use R)."""
    out = np.zeros((H, W, 3), np.uint8)
    bpr = W // 4
    for by in range(H//4):
        for bx in range(bpr):
            o = (by*bpr+bx)*16 + 8
            c0 = struct.unpack_from("<H", data, o)[0]
            c1 = struct.unpack_from("<H", data, o+2)[0]
            bits = int.from_bytes(data[o+4:o+8], "little")
            def rgb(c):
                r=((c>>11)&31)*255//31; g=((c>>5)&63)*255//63; b=(c&31)*255//31; return (r,g,b)
            c0r,c1r=rgb(c0),rgb(c1)
            if c0>c1:
                pal=[c0r,c1r,tuple((2*c0r[k]+c1r[k])//3 for k in range(3)),tuple((c0r[k]+2*c1r[k])//3 for k in range(3))]
            else:
                pal=[c0r,c1r,tuple((c0r[k]+c1r[k])//2 for k in range(3)),(0,0,0)]
            for i in range(16):
                out[by*4+i//4, bx*4+i%4]=pal[(bits>>(2*i))&3]
    return out

col = decode_bc1_color(blocks)
Image.fromarray(col, "RGB").save(os.path.join(SC,"atlas9_color.png"))
alpha = decode_alpha(blocks)

# A glyph box (from repurpose tests): (420,214)-(501,303). crop both channels big.
x0,y0,x1,y1 = 420,214,501,303
Image.fromarray(alpha[y0:y1,x0:x1],"L").resize((( x1-x0)*4,(y1-y0)*4),Image.NEAREST).save(os.path.join(SC,"A_alpha.png"))
Image.fromarray(col[y0:y1,x0:x1],"RGB").resize(((x1-x0)*4,(y1-y0)*4),Image.NEAREST).save(os.path.join(SC,"A_color.png"))

# scanline through the middle of the A (vertical center) - alpha values
midy = (y0+y1)//2
print("ALPHA scanline y=%d x=%d..%d:"%(midy,x0,x1))
print(" ".join("%3d"%v for v in alpha[midy, x0:x1]))
print("\nCOLOR(R) scanline same:")
print(" ".join("%3d"%v for v in col[midy, x0:x1, 0]))
# vertical scanline through left diagonal
midx = x0+20
print("\nALPHA vertical x=%d y=%d..%d:"%(midx,y0,y1))
print(" ".join("%3d"%v for v in alpha[y0:y1, midx]))
# histograms in the A box
print("\nA-box alpha unique:", [(int(v),int(c)) for v,c in zip(*np.unique(alpha[y0:y1,x0:x1],return_counts=True))][:12])
print("A-box color(R) unique:", [(int(v),int(c)) for v,c in zip(*np.unique(col[y0:y1,x0:x1,0],return_counts=True))][:12])
