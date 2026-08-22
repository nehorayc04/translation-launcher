# -*- coding: utf-8 -*-
import sys, struct
sys.path.insert(0, ".")
import numpy as np
from dpc_repack import DpcRepack
from inject_atlas import decode_alpha
DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
TEX1 = 0xEFC73FAE0445DAB6
D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
body = byid[TEX1].body
data = bytearray(body[0:512*512])   # CORRECT: data at 0
trailer = body[512*512:]
print("trailer (4 bytes):", trailer.hex(), " len", len(trailer))

def decode_bc1(data, W=512, H=512):
    out=np.zeros((H,W),np.uint8); bpr=W//4
    for by in range(H//4):
        for bx in range(bpr):
            o=(by*bpr+bx)*16+8
            c0=struct.unpack_from("<H",data,o)[0]; c1=struct.unpack_from("<H",data,o+2)[0]
            bits=int.from_bytes(data[o+4:o+8],"little")
            g0=((c0>>11)&31)*255//31; g1=((c1>>11)&31)*255//31
            if c0>c1: pal=[g0,g1,(2*g0+g1)//3,(g0+2*g1)//3]
            else: pal=[g0,g1,(g0+g1)//2,0]
            for i in range(16): out[by*4+i//4,bx*4+i%4]=pal[(bits>>(2*i))&3]
    return out
alpha=decode_alpha(data); col=decode_bc1(data)
print("ALPHA unique top:", [(int(v),int(c)) for v,c in sorted(zip(*[x[::-1] for x in [np.unique(alpha,return_counts=True)]][0]),reverse=True)][:1] if False else [(int(v),int(c)) for v,c in sorted(zip(*(lambda u:(u[1],u[0]))(np.unique(alpha,return_counts=True)),),reverse=True)[:6]])
print("COLOR unique top:", [(int(v),int(c)) for v,c in sorted(zip(*(lambda u:(u[1],u[0]))(np.unique(col,return_counts=True)),),reverse=True)[:6]])
# correlation: where alpha>128, what's color?
ink = alpha>128
print(f"ink pixels: color mean={col[ink].mean():.0f} min={col[ink].min()} max={col[ink].max()}")
print(f"bg  pixels: color mean={col[~ink].mean():.0f}")
# first block raw
print("block0 bytes:", data[0:16].hex(), " (alpha a0,a1=%d,%d ; color c0,c1=%04x,%04x)"%(data[0],data[1],struct.unpack_from('<H',data,8)[0],struct.unpack_from('<H',data,10)[0]))
