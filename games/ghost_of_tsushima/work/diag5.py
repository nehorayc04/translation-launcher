#!/usr/bin/env python3
"""Clean full scan with the PROVEN layout {u64 key, u32 off, u32 pad0}.
Count real records, split large-hash vs small-id, join EN<->AR on the FULL set,
and check the dialogue keys (small ids) align across languages."""
import os, struct, json
HERE=os.path.dirname(os.path.abspath(__file__)); GAME=os.path.dirname(HERE)
EN=os.path.join(GAME,"extract","lang_english_text.xpps")
AR=os.path.join(GAME,"extract","lang_arabic_text.xpps")

def is_ar(s): return any('؀'<=c<='ۿ' or 'ﭐ'<=c<='﷿' or 'ﹰ'<=c<='﻿' for c in s)
def has_letter(s): return any(c.isalpha() for c in s)

def scan(path):
    d=open(path,"rb").read()
    base=struct.unpack_from("<I",d,0x28)[0]; trailer=struct.unpack_from("<I",d,0x2c)[0]; N=len(d)
    # precompute valid string-start set (NUL-preceded, decodable, has a letter, len<=6000)
    def strat(off):
        p=base+off
        if p<=base or p>=trailer or d[p-1]!=0: return None
        e=d.find(b"\x00",p)
        if e<0 or e-p>6000: return None
        try: s=d[p:e].decode("utf-8")
        except: return None
        return s
    recs={}   # key -> (off, text)  last wins
    order=[]
    pos=0
    while pos<=N-16:
        key,off,pad=struct.unpack_from("<IxxxxII",d,pos) if False else struct.unpack_from("<QII",d,pos)
        if pad==0 and key!=0 and off>0 and off>>0<trailer:
            s=strat(off)
            if s is not None and (has_letter(s) or is_ar(s)):
                if key not in recs: order.append(key)
                recs[key]=(off,s)
                pos+=16; continue
        pos+=4
    return d,base,trailer,recs,order

dE,bE,tE,rE,oE=scan(EN)
dA,bA,tA,rA,oA=scan(AR)
big=lambda k:k>0xffffffff
print(f"EN clean records={len(rE)}  large-hash={sum(1 for k in rE if big(k))}  small-id={sum(1 for k in rE if not big(k))}")
print(f"AR clean records={len(rA)}  large-hash={sum(1 for k in rA if big(k))}  small-id={sum(1 for k in rA if not big(k))}")
common=set(rE)&set(rA)
print(f"overlap={len(common)}  EN_only={len(rE)-len(common)}  AR_only={len(rA)-len(common)}")
# alignment quality on FULL set: latin EN -> arabic AR, differ
lat=0;tr=0
for k in common:
    e=rE[k][1]; a=rA[k][1]
    if has_letter(e) and any('a'<=c.lower()<='z' for c in e):
        lat+=1
        if is_ar(a) and a!=e: tr+=1
print(f"common w/ latin-EN={lat}  of which AR is arabic&differs={tr}  ({round(100*tr/lat,1)}%)")
# split by key kind for scope
big_common=[k for k in common if big(k)]
small_common=[k for k in common if not big(k)]
print(f"overlap large-hash(UI/content)={len(big_common)}  small-id(dialogue)={len(small_common)}")

# check DIALOGUE small-id alignment: 10 pairs
print("\n-- 10 DIALOGUE (small-id) pairs, CORRECT layout --")
shown=0
for k in sorted(small_common):
    e=rE[k][1]; a=rA[k][1]
    if any('a'<=c.lower()<='z' for c in e) and is_ar(a) and 2<len(e)<45:
        print(f"   key={k:012x} EN={e!r} AR={a!r}"); shown+=1
    if shown>=10: break
# specifically the ones OLD misaligned:
print("\n-- keys OLD misaligned, now CORRECT --")
for kk in [0x50000,0x300000]:
    print(f"   key={kk:x} EN={rE.get(kk,('','<none>'))[1]!r} AR={rA.get(kk,('','<none>'))[1]!r}")

json.dump({"EN":len(rE),"AR":len(rA),"overlap":len(common),
           "overlap_large_hash_UI":len(big_common),"overlap_small_id_dialogue":len(small_common),
           "EN_large":sum(1 for k in rE if big(k)),"EN_small":sum(1 for k in rE if not big(k))},
          open(os.path.join(HERE,"scope_out.json"),"w"),indent=1)
print("\nwrote scope_out.json")
