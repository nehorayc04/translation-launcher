#!/usr/bin/env python3
"""Total record volume (not deduped) + confirm large-hash UI join is ~100% correct
+ prove small-id keys collide (per-block, non-global). Also bidi double-check on UI word."""
import os, struct
HERE=os.path.dirname(os.path.abspath(__file__)); GAME=os.path.dirname(HERE)
EN=os.path.join(GAME,"extract","lang_english_text.xpps")
AR=os.path.join(GAME,"extract","lang_arabic_text.xpps")
def is_ar(s): return any('؀'<=c<='ۿ' or 'ﭐ'<=c<='﷿' or 'ﹰ'<=c<='﻿' for c in s)
def has_letter(s): return any(c.isalpha() for c in s)

def scan_all(path):
    d=open(path,"rb").read()
    base=struct.unpack_from("<I",d,0x28)[0]; trailer=struct.unpack_from("<I",d,0x2c)[0]; N=len(d)
    def strat(off):
        p=base+off
        if p<=base or p>=trailer or d[p-1]!=0: return None
        e=d.find(b"\x00",p)
        if e<0 or e-p>6000: return None
        try: s=d[p:e].decode("utf-8")
        except: return None
        return s
    total=0; big=0; small=0; small_dup=0
    seen_small={}
    pos=0
    while pos<=N-16:
        key,off,pad=struct.unpack_from("<QII",d,pos)
        if pad==0 and key!=0 and off>0 and off<trailer:
            s=strat(off)
            if s is not None and (has_letter(s) or is_ar(s)):
                total+=1
                if key>0xffffffff: big+=1
                else:
                    small+=1
                    seen_small[key]=seen_small.get(key,0)+1
                pos+=16; continue
        pos+=4
    small_collisions=sum(v-1 for v in seen_small.values() if v>1)
    return d,base,trailer,total,big,small,len(seen_small),small_collisions

for p,l in [(EN,"EN"),(AR,"AR")]:
    d,b,t,tot,big,sm,smu,smc=scan_all(p)
    print(f"{l}: TOTAL records={tot}  large-hash={big}  small-id records={sm} "
          f"(unique small keys={smu}, collided extra={smc})")

# Prove UI large-hash join ~100% correct: for all shared large-hash keys, how many
# have AR arabic + differ (translated) vs identical (untranslated/passthrough)
def read_big(path):
    d=open(path,"rb").read(); base=struct.unpack_from("<I",d,0x28)[0]; trailer=struct.unpack_from("<I",d,0x2c)[0]; N=len(d)
    def strat(off):
        p=base+off
        if p<=base or p>=trailer or d[p-1]!=0: return None
        e=d.find(b"\x00",p);
        if e<0 or e-p>6000: return None
        try:return d[p:e].decode("utf-8")
        except:return None
    m={}; pos=0
    while pos<=N-16:
        key,off,pad=struct.unpack_from("<QII",d,pos)
        if pad==0 and key>0xffffffff and off>0 and off<trailer:
            s=strat(off)
            if s is not None and (has_letter(s) or is_ar(s)):
                m[key]=s; pos+=16; continue
        pos+=4
    return m
E=read_big(EN); A=read_big(AR); com=set(E)&set(A)
lat=[k for k in com if any('a'<=c.lower()<='z' for c in E[k])]
tr=sum(1 for k in lat if is_ar(A[k]) and A[k]!=E[k])
same=sum(1 for k in lat if A[k]==E[k])
print(f"\nLARGE-HASH UI join: shared={len(com)} latin-EN={len(lat)} "
      f"-> AR-arabic&differs={tr} ({round(100*tr/len(lat),1)}%)  identical(passthrough)={same}")
# the identical ones — sample (should be names/codes)
ids=[k for k in lat if A[k]==E[k]][:8]
for k in ids: print(f"   passthrough key={k:016x} {E[k]!r}")
