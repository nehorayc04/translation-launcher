# -*- coding: utf-8 -*-
import sys, os, struct
sys.path.insert(0, ".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from inject_atlas import decode_alpha, resolve_mat_textures, TEX_CLASS

DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
SC = r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad"
os.makedirs(SC, exist_ok=True)

D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fm = byid[BIG]; fz = FontsZ(fm.body)
m2t = resolve_mat_textures(byid, fz)
print("mat->tex:", {k: "%016X"%v for k,v in m2t.items()})

texids = sorted({v for v in m2t.values()})
for i, tid in enumerate(texids):
    t = byid[tid]
    body = t.body
    # dims from info: width @ offset? we saw 512,512. verify body size
    n = len(body) - 4
    side = int(round((n) ** 0.5))
    a = decode_alpha(bytearray(body[4:]), side, side)
    Image.fromarray(a, "L").save(os.path.join(SC, f"atlas_{i}_{tid:016X}.png"))
    # bg stats + occupancy
    vals, cnts = np.unique(a, return_counts=True)
    top = sorted(zip(cnts, vals), reverse=True)[:5]
    ink = int((a > 128).sum())
    print(f"page{i} {tid:016X} side={side} top_vals(cnt,val)={[(int(c),int(v)) for c,v in top]} ink>128={ink} ({100*ink/a.size:.1f}%)")

# also: which mat indices are actually USED by non-arabic glyphs (Latin/digits/tokens)?
def is_ar(cp): return 0x0600<=cp<=0x06FF or 0xFB50<=cp<=0xFEFF
used_mats = {}
for e in fz.entries:
    c = cid_to_char(e.cid)
    kind = "arabic" if (c and is_ar(ord(c[0]))) else "other"
    used_mats.setdefault(e.mat, {"arabic":0,"other":0})[kind]+=1
print("\nmat usage (arabic vs other glyphs):")
for m in sorted(used_mats): print(f"  mat{m}: {used_mats[m]}")
