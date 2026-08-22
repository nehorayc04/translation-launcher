#!/usr/bin/env python3
"""Resolve TRUE scope: are ~27k pool strings unindexed (missed dialogue) or fragments?
Scan for ALL index records under the {u64 key,u64 off} layout WITHOUT the ascending
constraint, count referenced vs orphaned pool offsets."""
import os, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__)); GAME=os.path.dirname(HERE)
EN=os.path.join(GAME,"extract","lang_english_text.xpps")
AR=os.path.join(GAME,"extract","lang_arabic_text.xpps")

def analyze(path,label):
    d=open(path,"rb").read()
    base=struct.unpack_from("<I",d,0x28)[0]
    trailer=struct.unpack_from("<I",d,0x2c)[0]
    N=len(d)
    # 1. Enumerate every pool-string START offset (pool = base..trailer),
    #    a start = position preceded by NUL (or ==base), decodable, nonempty.
    starts=set()
    i=base
    # find chunk starts by splitting on NUL
    p=base
    while p<trailer:
        e=d.find(b"\x00",p)
        if e<0: e=trailer
        chunk=d[p:e]
        if chunk:
            try:
                s=chunk.decode("utf-8")
                if s.strip():
                    starts.add(p-base)   # store as pool-relative offset
            except: pass
        p=e+1
    # 2. Scan the WHOLE file for 16B records {u64 key, u64 off} where off (pool-rel)
    #    lands EXACTLY on a known string start and key looks like a hash/id.
    ref=set(); reckeys=[]
    for pos in range(0,N-16,4):
        key,off=struct.unpack_from("<QQ",d,pos)
        if off>>32==0 and off in starts and (key>>32==0 or key>0):
            # cheap plausibility: key nonzero
            if key!=0:
                ref.add(off); reckeys.append(key)
    print(f"\n== {label}: size={N} base={base} trailer={trailer}")
    print(f"   pool string-starts (NUL-split, decodable, nonempty) = {len(starts)}")
    print(f"   distinct offsets referenced by any {{u64,u64off}} record hitting a start = {len(ref)}")
    print(f"   orphan starts (present but never referenced) = {len(starts-ref)}")
    # sample orphans
    orph=sorted(starts-ref)[:8]
    for o in orph:
        e=d.find(b"\x00",base+o); s=d[base+o:e].decode("utf-8","replace")
        print(f"      orphan @pool+{o}: {s[:50]!r}")
    return d,base,trailer,starts,ref

for p,l in [(EN,"EN"),(AR,"AR")]:
    analyze(p,l)
