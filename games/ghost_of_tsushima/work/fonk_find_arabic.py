#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_find_arabic.py — find a LARGE stride-64 ascending-cp run reaching Arabic/CJK.
Criteria: each record's u16@+2==0 (cp high bytes zero), run>=MINRUN contiguous ascending
records, reports coverage. Cuts mesh noise by requiring long clean runs + +2==0."""
import os, sys, struct
import numpy as np
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R
GREC=64
def get(a,n):
    arc=R.Psarc2(os.path.join(PD,a)); t=next((e for e in arc.files() if e.path.rstrip('/').endswith(n)),None)
    d=arc.extract(t) if t else None; arc.d.f.close(); return d
def runs(data, minrun=25):
    n=len(data); out=[]
    b=np.frombuffer(data,dtype=np.uint8)
    # candidate positions: u16@+2==0 (byte+2==0 and +3==0) and cp in 1..0xfffe
    # find where record start could be: we detect ascending runs directly.
    # For speed: view as records is not aligned; do a sliding check over all offsets where
    #   data[p+2]==0 and data[p+3]==0 (cp hi zero) and data[p]!=0
    cand=np.nonzero((b[2:-1]==0)&(b[3:]==0))[0]  # offset p where p+2,p+3==0
    candset=set(int(x) for x in cand)
    visited=set()
    for p in sorted(candset):
        if p in visited: continue
        if p+GREC>n: continue
        cp0=struct.unpack_from("<H",data,p)[0]
        if not (1<=cp0<=0xfffe): continue
        # is p a run start? (p-GREC not an ascending predecessor)
        if (p-GREC)>=0:
            pcp=struct.unpack_from("<H",data,p-GREC)[0]
            if (p-GREC) in candset and pcp==cp0-1: 
                continue
        cps=[]; q=p
        while q+GREC<=n:
            if not (q+3<len(data) and data[q+2]==0 and data[q+3]==0): break
            c=struct.unpack_from("<H",data,q)[0]
            if c==0xffff: break
            if cps and c<=cps[-1]: break
            if not (1<=c<=0xfffe): break
            cps.append(c); visited.add(q); q+=GREC
        if len(cps)>=minrun:
            out.append((p,cps))
    return out
def summ(cps):
    def rng(a,bb): return sum(1 for c in cps if a<=c<=bb)
    return (f"n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}] ASCII={rng(0x20,0x7e)} "
            f"Heb={rng(0x5d0,0x5ea)} Arabic={rng(0x600,0x6ff)} ArPF={rng(0xfb50,0xfeff)} "
            f"Hira={rng(0x3040,0x309f)} CJK={rng(0x4e00,0x9fff)}")
if __name__=="__main__":
    archive,suffix=sys.argv[1],sys.argv[2]
    minrun=int(sys.argv[3]) if len(sys.argv)>3 else 25
    data=get(archive,suffix)
    if data is None: print("NOT FOUND"); sys.exit(1)
    print(f"{suffix} [{archive}] {len(data):,}B magic={data[:4]!r}")
    rr=runs(data,minrun)
    # show runs reaching arabic/cjk/hebrew, then the biggest few
    ar=[t for t in rr if max(t[1])>=0x5d0]
    print(f"total runs>={minrun}: {len(rr)};  runs reaching >=0x5d0 (Heb/Arabic/CJK): {len(ar)}")
    for p,cps in sorted(ar,key=lambda t:-len(t[1]))[:15]:
        print(f"  @0x{p:x} {summ(cps)}")
    print("  --- biggest runs overall ---")
    for p,cps in sorted(rr,key=lambda t:-len(t[1]))[:6]:
        print(f"  @0x{p:x} {summ(cps)}")
