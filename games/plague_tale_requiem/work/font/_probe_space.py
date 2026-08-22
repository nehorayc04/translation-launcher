# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,".")
import numpy as np
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
from build_hebrew_font import decode_alpha, resolve_mat_textures, is_ar, NPIX, SIDE, fit_font, render_letter, HEBREW, DEF_FONT
DPC=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG=0xAFBE3792DDA3B358
D=DpcRepack(DPC+".he_backup")
byid={o.oid:o for o in (list(D.db_objs)+[o for _,o,_ in D.fb_objs])}
fz=FontsZ(byid[BIG].body); m2t=resolve_mat_textures(byid,fz)

# arabic slot size distribution
ars=[e for e in fz.entries if (lambda c:c and is_ar(ord(c[0])))(cid_to_char(e.cid))]
sizes=sorted([(int(e.x1-e.x0),int(e.y1-e.y0)) for e in ars], key=lambda t:-t[0]*t[1])
print("top 30 arabic slot sizes (w,h):", sizes[:30])
for W,H in [(48,72),(44,66),(40,60),(36,54)]:
    n=sum(1 for w,h in sizes if w>=W and h>=H)
    print(f"  slots >= {W}x{H}: {n}")

# glyph sizes at various targets
for tgt in [64,52,44,38]:
    import build_hebrew_font as B
    B.BODY_TARGET=tgt
    f=B.fit_font(DEF_FONT)
    gs={ch:B.render_letter(f,ch) for ch in HEBREW}
    mw=max(g.shape[1] for g,_ in gs.values()); mh=max(g.shape[0] for g,_ in gs.values())
    print(f"BODY_TARGET={tgt} size={f.size}: max_w={mw} max_h={mh}")

# largest empty square per page (coarse: 4x4 block occupancy)
print("\nempty space per page (biggest empty axis-aligned rect via block grid):")
for i,tex in enumerate(sorted(set(m2t.values()))):
    a=decode_alpha(bytearray(byid[tex].body[:NPIX]))
    # block occupancy 128x128
    blk=(a.reshape(128,4,128,4).max(axis=(1,3))>60)  # True=ink
    # largest all-empty rectangle (histogram method) in block units
    H,W=blk.shape; heights=[0]*W; best=(0,0,0)
    for r in range(H):
        for c in range(W): heights[c]=0 if blk[r,c] else heights[c]+1
        st=[]; 
        for c in range(W+1):
            cur=heights[c] if c<W else 0
            start=c
            while st and st[-1][1]>=cur:
                sc,sh=st.pop(); area=sh*(c-sc)
                if area>best[0]: best=(area,sh,c-sc)
                start=sc
            st.append((start,cur))
    print(f" page{i} {tex:016X}: biggest empty {best[1]*4}x{best[2]*4}px (area {best[0]*16}px blocks)")
