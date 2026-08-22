#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_cmaphunt.py — detect CMAP-style glyph tables (core_common format): 64-byte
records where u16@+0 (cp) == u16@+62, cp ascending, run>=MINRUN. Format-based (not
cp-seeded) so pure-Arabic/CJK cmap tables are found. Usage: <archive> <name> [minrun]"""
import os,sys,struct
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R
GAME=os.environ.get("GOT_GAME",r"F:/Games/Ghost of Tsushima DC"); PD=os.path.join(GAME,"cache_pc","psarc")
GREC=64
def get(a,n):
    arc=R.Psarc2(os.path.join(PD,a)); t=next((e for e in arc.files() if e.path.rstrip('/').endswith(n)),None)
    d=arc.extract(t) if t else None; arc.d.f.close(); return d
def cmap_rec(data,p):
    if p+GREC>len(data): return None
    cp=struct.unpack_from("<H",data,p)[0]
    if struct.unpack_from("<H",data,p+2)[0]!=0: return None
    if struct.unpack_from("<H",data,p+62)[0]!=cp: return None   # cp echoed at +62
    return cp
def find(data,minrun=16):
    n=len(data); out=[]; used=set()
    b=np.frombuffer(data,dtype=np.uint8)
    # candidate: byte+2==0 & byte+3==0 (cp hi zero). check cmap sig on each.
    cand=np.nonzero((b[2:-1]==0)&(b[3:]==0))[0]
    for p in cand:
        p=int(p)
        if p in used: continue
        cp=cmap_rec(data,p)
        if cp is None or not(1<=cp<=0xfffe): continue
        # start only
        if p-GREC>=0 and cmap_rec(data,p-GREC)==cp-1: continue
        cps=[]; q=p
        while q+GREC<=n:
            c=cmap_rec(data,q)
            if c is None: break
            if cps and c<=cps[-1]: break
            if not(1<=c<=0xfffe): break
            cps.append(c); used.add(q); q+=GREC
        if len(cps)>=minrun: out.append((p,cps))
    return out
def rng(cps,x,y): return sum(1 for c in cps if x<=c<=y)
if __name__=="__main__":
    a,n=sys.argv[1],sys.argv[2]; mr=int(sys.argv[3]) if len(sys.argv)>3 else 16
    data=get(a,n)
    if data is None: print("NOT FOUND"); sys.exit(1)
    tbls=find(data,mr)
    inter=[t for t in tbls if max(t[1])>=0x400]
    print(f"{n}: {len(data):,}B  {len(tbls)} CMAP tables; reaching cp>=0x400: {len(inter)}")
    for p,cps in sorted(inter,key=lambda t:-len(t[1]))[:15]:
        print(f"  @0x{p:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}] "
              f"Heb={rng(cps,0x5d0,0x5ea)} Ar={rng(cps,0x600,0x6ff)} ArPF={rng(cps,0xfb50,0xfeff)} "
              f"Hira={rng(cps,0x3040,0x309f)} CJK={rng(cps,0x4e00,0x9fff)}")
    if not inter:
        for p,cps in sorted(tbls,key=lambda t:-len(t[1]))[:5]:
            print(f"  (Latin) @0x{p:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}]")
