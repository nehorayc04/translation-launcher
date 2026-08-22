#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, struct
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R
def get(a,n):
    arc=R.Psarc2(os.path.join(PD,a)); t=next((e for e in arc.files() if e.path.rstrip('/').endswith(n)),None)
    d=arc.extract(t) if t else None; arc.d.f.close(); return d
GREC=64
data=get("gapack_misc_m.psarc","m_lm_menu.sprig.xpps")
TBL=0x4223e
# build cp->fileoffset
recs={}
q=TBL
while q+GREC<=len(data):
    cp=struct.unpack_from("<H",data,q)[0]
    if cp==0xffff: break
    if recs and cp<=max(recs): 
        # only continue while ascending; but store by cp
        pass
    recs[cp]=q; q+=GREC
print(f"{len(recs)} records. cp range 0x{min(recs):x}..0x{max(recs):x}")
def show(cp):
    if cp not in recs: print(f"cp 0x{cp:x} not present"); return
    o=recs[cp]; r=data[o:o+GREC]
    m=struct.unpack_from("<f",r,4)[0]
    print(f"\ncp=0x{cp:x}({chr(cp) if 32<=cp<127 else '?'}) @0x{o:x}  metric(+4 f32)={m:.4f}")
    print("  "+r.hex())
    # words
    ws=[]
    for w in range(16):
        u=struct.unpack_from('<I',r,w*4)[0]; f=struct.unpack_from('<f',r,w*4)[0]
        ws.append(f"+{w*4}:{u:08x}")
    print("  "+" ".join(ws))
for cp in (0x20,0x2e,0x41,0x42,0x49,0x4d,0x6c,0x69,0x57,0x6d):
    show(cp)
# check: how many DISTINCT geometry(+22..46) blocks across all glyphs?
geo={}
for cp,o in recs.items():
    g=data[o+22:o+46]; geo.setdefault(g,[]).append(cp)
print(f"\n{len(recs)} glyphs -> {len(geo)} distinct +22..46 blocks")
for g,cps in sorted(geo.items(), key=lambda kv:-len(kv[1]))[:6]:
    print(f"   {len(cps)} glyphs share: {' '.join(chr(c) if 32<=c<127 else hex(c) for c in cps[:20])}")
    print(f"      bytes={g.hex()}")
