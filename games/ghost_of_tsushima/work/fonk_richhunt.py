#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_richhunt.py — run got_fonk.find_rich_tables (validated, low-FP) on a package
file and report any table reaching Arabic/Hebrew/CJK. Usage: <archive> <name> [minrun]"""
import os,sys
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
sys.path.insert(0,os.path.join(HERE,"..","..","tlou2","tools"))
import got_fonk as F, dsar as R
GAME=os.environ.get("GOT_GAME",r"F:/Games/Ghost of Tsushima DC"); PD=os.path.join(GAME,"cache_pc","psarc")
def get(a,n):
    arc=R.Psarc2(os.path.join(PD,a)); t=next((e for e in arc.files() if e.path.rstrip('/').endswith(n)),None)
    d=arc.extract(t) if t else None; arc.d.f.close(); return d
a,n=sys.argv[1],sys.argv[2]; mr=int(sys.argv[3]) if len(sys.argv)>3 else 16
data=get(a,n)
if data is None: print("NOT FOUND"); sys.exit(1)
tbls=F.find_rich_tables(data,mr)
def rng(cps,x,y): return sum(1 for c in cps if x<=c<=y)
print(f"{n}: {len(data):,}B  {len(tbls)} RICH tables (min_run={mr})")
inter=[t for t in tbls if max(t[1])>=0x400]
print(f"  tables reaching cp>=0x400 (beyond Latin): {len(inter)}")
for s,cps,e in sorted(tbls,key=lambda t:-len(t[1]))[:20]:
    tag=(f"ASCII={rng(cps,0x20,0x7e)} Heb={rng(cps,0x5d0,0x5ea)} Ar={rng(cps,0x600,0x6ff)} "
         f"ArPF={rng(cps,0xfb50,0xfeff)} Hira={rng(cps,0x3040,0x309f)} CJK={rng(cps,0x4e00,0x9fff)}")
    print(f"  @0x{s:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}] {tag}")
