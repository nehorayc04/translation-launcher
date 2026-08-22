#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_hunt_strict.py — find REAL 64-byte glyph tables using the record SIGNATURE
(from m_lm_menu/core_common): +8 u32==4, +62 u16==0xffff, and the 3 trailing color
floats +50/+54/+58 == 1.0 (0x3f800000). Report script coverage. This rejects mesh noise.
Usage: fonk_hunt_strict.py <archive.psarc> <name-suffix> [min_run]"""
import os, sys, struct
import numpy as np
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R
GREC=64
def get(a,n):
    arc=R.Psarc2(os.path.join(PD,a)); t=next((e for e in arc.files() if e.path.rstrip('/').endswith(n)),None)
    d=arc.extract(t) if t else None; arc.d.f.close(); return d

def is_rec(data,p):
    if p+GREC>len(data): return False
    if struct.unpack_from("<I",data,p+8)[0]!=4: return False
    if struct.unpack_from("<H",data,p+62)[0]!=0xffff: return False
    # trailing color: +50,+54,+58 == 1.0
    for o in (50,54,58):
        if struct.unpack_from("<I",data,p+o)[0]!=0x3f800000: return False
    return True

def find_tables(data, min_run=8):
    """Scan every 2-byte position as a potential record with valid signature; group
    consecutive valid records with ascending cp into tables."""
    n=len(data); tables=[]; i=0
    # fast prefilter: candidate record starts where u32@+8==4 (bytes 04 00 00 00)
    b=np.frombuffer(data,dtype=np.uint8)
    # positions p where data[p+8:p+12]==04 00 00 00  -> p = q-8
    q=np.nonzero((b[:-3]==0x04)&(b[1:-2]==0)&(b[2:-1]==0)&(b[3:]==0))[0]
    cand=set(int(x)-8 for x in q if int(x)-8>=0)
    starts=sorted(cand)
    used=set()
    for p in starts:
        if p in used: continue
        if not is_rec(data,p): continue
        # ensure this is a table START (prev record not valid+ascending)
        cp=struct.unpack_from("<H",data,p)[0]
        prev_ok = (p-GREC>=0 and is_rec(data,p-GREC) and
                   struct.unpack_from("<H",data,p-GREC)[0]==cp-1)
        if prev_ok: continue
        # walk forward
        cps=[]; q2=p
        while q2+GREC<=n and is_rec(data,q2):
            c=struct.unpack_from("<H",data,q2)[0]
            if c==0xffff: cps.append(c); used.add(q2); q2+=GREC; break
            if cps and c<=cps[-1]: break
            cps.append(c); used.add(q2); q2+=GREC
        real=[c for c in cps if c!=0xffff]
        if len(real)>=min_run:
            tables.append((p,q2,real))
    return tables

def summ(real):
    def rng(a,bb): return sum(1 for c in real if a<=c<=bb)
    return (f"n={len(real)} cp[0x{min(real):x}..0x{max(real):x}] ASCII={rng(0x20,0x7e)} "
            f"Lat1={rng(0x80,0xff)} LatExt={rng(0x100,0x24f)} Hebrew={rng(0x5d0,0x5ea)} "
            f"Arabic={rng(0x600,0x6ff)} ArPF={rng(0xfb50,0xfeff)} "
            f"Hira={rng(0x3040,0x309f)} Kata={rng(0x30a0,0x30ff)} CJK={rng(0x4e00,0x9fff)}")

if __name__=="__main__":
    archive, suffix = sys.argv[1], sys.argv[2]
    min_run=int(sys.argv[3]) if len(sys.argv)>3 else 8
    data=get(archive,suffix)
    if data is None: print("NOT FOUND"); sys.exit(1)
    print(f"{suffix} [{archive}] {len(data):,}B magic={data[:4]!r}")
    tbls=find_tables(data,min_run)
    print(f"found {len(tbls)} VALIDATED glyph tables (signature-checked)")
    # sort by size desc
    for s,e,real in sorted(tbls,key=lambda t:-len(t[2]))[:30]:
        print(f"  @0x{s:x} {summ(real)}")
