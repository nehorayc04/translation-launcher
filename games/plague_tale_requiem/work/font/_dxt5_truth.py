# -*- coding: utf-8 -*-
import sys, io, struct
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from inject_atlas import decode_alpha
from roundtrip_test import enc_alpha_adaptive

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
TEX1 = 0xEFC73FAE0445DAB6
D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
body = byid[TEX1].body
print("body len", len(body), "=> 4 +", len(body)-4, " (512*512 =", 512*512, ")")

def make_dds(dxt5_bytes, w=512, h=512):
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    struct.pack_into("<I", hdr, 4, 124)          # dwSize
    struct.pack_into("<I", hdr, 8, 0x1|0x2|0x4|0x1000|0x80000)  # flags: caps,height,width,pixelformat,linearsize
    struct.pack_into("<I", hdr, 12, h)
    struct.pack_into("<I", hdr, 16, w)
    struct.pack_into("<I", hdr, 20, len(dxt5_bytes))  # linear size
    struct.pack_into("<I", hdr, 28, 1)           # mipcount
    # pixelformat at offset 76
    struct.pack_into("<I", hdr, 76, 32)          # pf size
    struct.pack_into("<I", hdr, 80, 0x4)         # DDPF_FOURCC
    hdr[84:88] = b"DXT5"
    struct.pack_into("<I", hdr, 108, 0x1000)     # caps texture
    return bytes(hdr) + bytes(dxt5_bytes)

def pillow_decode(dxt5_bytes):
    im = Image.open(io.BytesIO(make_dds(dxt5_bytes))).convert("RGBA")
    return np.array(im)   # H,W,4  (RGBA); alpha = [...,3]

# hypothesis A: real DXT5 is body[4:], my usual decode
blocks_skip4 = bytearray(body[4:])
# hypothesis B: real DXT5 is body[0:262144] (4-byte TRAILER not prefix)
blocks_no = bytearray(body[0:512*512])

for name, blk in [("SKIP4(body[4:])", blocks_skip4), ("NOSKIP(body[:262144])", blocks_no)]:
    try:
        px = pillow_decode(blk)
        a = px[...,3]; r = px[...,0]
        # occupancy of alpha and 'cleanliness' (how bimodal): fraction near 0 or 255
        binf = ((a<20)|(a>235)).mean()
        print(f"[{name}] Pillow OK. alpha: bg-ish(<20)={(a<20).mean():.2f} ink(>235)={(a>235).mean():.2f} bimodal={binf:.2f}  meanA={a.mean():.0f}")
        Image.fromarray(a,"L").save(f"_pil_{name.split('(')[0]}_alpha.png")
        Image.fromarray(r,"L").save(f"_pil_{name.split('(')[0]}_red.png")
    except Exception as e:
        print(f"[{name}] Pillow FAIL: {e}")

# Compare MY decoder vs Pillow on the SAME (skip4) bytes -> validate my decoder == GPU
mine = decode_alpha(blocks_skip4)
pil = pillow_decode(blocks_skip4)[...,3]
d = np.abs(mine.astype(int)-pil.astype(int))
print(f"\nMY decoder vs Pillow (skip4 alpha): max={d.max()} mean={d.mean():.2f} disagree>4={ (d>4).mean()*100:.2f}%")

# Now: re-encode with my adaptive, decode via PILLOW (the GPU truth) and compare to original-via-Pillow
re = bytearray(blocks_skip4)
bpr=128
al = decode_alpha(blocks_skip4)
for by in range(128):
    for bx in range(128):
        o=(by*bpr+bx)*16
        re[o:o+8]=enc_alpha_adaptive(al[by*4:by*4+4,bx*4:bx*4+4])
pil_orig = pillow_decode(blocks_skip4)[...,3]
pil_mine = pillow_decode(re)[...,3]
d2 = np.abs(pil_orig.astype(int)-pil_mine.astype(int))
print(f"GPU-view: orig vs MY-reencode: max={d2.max()} mean={d2.mean():.2f} changed>16={(d2>16).mean()*100:.2f}%")
Image.fromarray(pil_orig,"L").save("_gpu_orig_alpha.png")
Image.fromarray(pil_mine,"L").save("_gpu_mine_alpha.png")
Image.fromarray((d2*3).clip(0,255).astype(np.uint8),"L").save("_gpu_diff.png")
