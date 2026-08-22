#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_hunt_script.py — hunt 64-byte glyph tables in a KCAP xpps by seeding on ANY
codepoint (not just 'A'), so pure-Arabic / pure-CJK tables are found. Reports script
coverage per table. Usage: fonk_hunt_script.py <archive.psarc> <name-suffix>"""
import os, sys, struct
import numpy as np
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R
GREC=64

def get(archive,name):
    arc=R.Psarc2(os.path.join(PD,archive))
    tgt=next((e for e in arc.files() if e.path.rstrip("/").endswith(name)),None)
    data=arc.extract(tgt) if tgt else None
    arc.d.f.close(); return data

def table_at(data, s):
    """walk back to table start, then forward collecting cps; return (start,end,cps)."""
    # walk back while previous cp == cur-1
    p=s
    while p-GREC>=0:
        a=struct.unpack_from("<H",data,p-GREC)[0]; c=struct.unpack_from("<H",data,p)[0]
        if a==c-1 and 1<=a<=0xfffe: p-=GREC
        else: break
    q=p; cps=[]
    while q+GREC<=len(data):
        cp=struct.unpack_from("<H",data,q)[0]
        if cp==0xffff: cps.append(cp); q+=GREC; break
        if cps and cp<=cps[-1]: break
        if not (1<=cp<=0xfffe): break
        cps.append(cp); q+=GREC
    return p,q,cps

def hunt(data, seeds_cp):
    b=np.frombuffer(data,dtype=np.uint8)
    found={}
    for cp in seeds_cp:
        lo=cp & 0xff; hi=(cp>>8)&0xff
        idx=np.nonzero((b[:-1]==lo)&(b[1:]==hi))[0]
        for p in idx:
            p=int(p)
            # require a 64-strided ascending neighbor to reduce false positives
            if p+2*GREC+2>len(data): continue
            c1=struct.unpack_from("<H",data,p+GREC)[0]
            if not (c1==cp+1): continue
            s,e,cps=table_at(data,p)
            if len(cps)>=6: found[s]=(e,cps)
    return found

def summ(cps):
    real=[c for c in cps if c!=0xffff]
    def rng(a,bb): return sum(1 for c in real if a<=c<=bb)
    return (f"n={len(real)} cp[0x{min(real):x}..0x{max(real):x}] ASCII={rng(0x20,0x7e)} "
            f"Lat1={rng(0x80,0xff)} Hebrew={rng(0x5d0,0x5ea)} Arabic={rng(0x600,0x6ff)} "
            f"ArPF={rng(0xfb50,0xfeff)} CJK={rng(0x3000,0x9fff)} Hira={rng(0x3040,0x309f)} "
            f"Kata={rng(0x30a0,0x30ff)}")

if __name__=="__main__":
    archive, suffix = sys.argv[1], sys.argv[2]
    data=get(archive,suffix)
    if data is None: print("NOT FOUND"); sys.exit(1)
    print(f"{suffix} [{archive}] {len(data):,}B magic={data[:4]!r}")
    # seed on: Arabic alef/beh/lam/meem/teh, Hebrew alef, Hiragana a, Katakana a, CJK common, Latin A
    seeds=[0x627,0x628,0x644,0x645,0x62a, 0x5d0,0x5d1, 0x3042,0x3044, 0x30a2, 0x4e00,0x611b, 0x41,0x30]
    found=hunt(data,seeds)
    print(f"found {len(found)} tables (multi-cp seed)")
    for s in sorted(found):
        e,cps=found[s]; print(f"  @0x{s:x} {summ(cps)}")
