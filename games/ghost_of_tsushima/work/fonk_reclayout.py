#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_reclayout.py — nail the 64-byte glyph record layout: dump many records from
m_lm_menu's Latin table, tabulate every 4-byte word (u32/f32/2xu16), mark constant vs
varying columns, and check whether +22..+46 is inline coords or an external ref."""
import os, sys, struct
import numpy as np
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import dsar as R
def get(a,n):
    arc=R.Psarc2(os.path.join(PD,a)); t=next((e for e in arc.files() if e.path.rstrip('/').endswith(n)),None)
    d=arc.extract(t) if t else None; arc.d.f.close(); return d
GREC=64
data=get("gapack_misc_m.psarc","m_lm_menu.sprig.xpps")
TBL=0x4223e
# collect records
recs=[]
q=TBL
while q+GREC<=len(data):
    cp=struct.unpack_from("<H",data,q)[0]
    if recs and cp!=0xffff and cp<=recs[-1][0]: break
    recs.append((cp, data[q:q+GREC], q)); 
    if cp==0xffff: break
    q+=GREC
print(f"table @0x{TBL:x}: {len(recs)} records, last cp=0x{recs[-1][0]:x}")
# tabulate per 4-byte word: which columns are constant across all non-sentinel records
body=[r[1] for r in recs if r[0]!=0xffff]
print(f"\nPer-word analysis over {len(body)} glyph records (16 words x 4B):")
print("word off | constant? | sampleA(0x41) as u32 / f32 / 2xu16")
for w in range(16):
    off=w*4
    vals=set(rr[off:off+4] for rr in body)
    const = len(vals)==1
    # sample from 'A' record
    arec=next(rr for cp,rr,_ in recs if cp==0x41)
    u32=struct.unpack_from("<I",arec,off)[0]
    f32=struct.unpack_from("<f",arec,off)[0]
    h0,h1=struct.unpack_from("<HH",arec,off)
    flag = "CONST" if const else f"vary({len(vals)})"
    print(f"  +{off:2d} | {flag:9s} | u32=0x{u32:08x} f32={f32:.4g} u16=(0x{h0:x},0x{h1:x})")
# Now: is +22..+46 an offset/count into a bigger array? check if any 4-byte word looks
# like a monotonic offset across glyphs, or a small count.
print("\n== scan for offset-like / count-like columns (byte-granular, +20..+46) ==")
for off in range(20,46,2):
    col=[struct.unpack_from("<I",rr,off)[0] for rr in body if off+4<=GREC]
    # count-like: small ints
    small=[c for c in col if c<4096]
    mono = all(col[i]<=col[i+1] for i in range(len(col)-1))
    if len(small)>len(col)*0.6 or mono:
        print(f"  +{off}: small-int frac={len(small)/len(col):.2f} monotonic={mono} sample={col[:8]}")
# dump the raw geometry region for A, B, I (simple), M (complex), space, period
print("\n== geometry bytes +20..+46 for sample glyphs ==")
for cp in (0x20,0x2e,0x41,0x42,0x49,0x4d,0x6c,0x69):
    rr=next((r for c,r,_ in recs if c==cp),None)
    if rr: print(f"  cp=0x{cp:x}({chr(cp)}): {rr[20:46].hex()}")
