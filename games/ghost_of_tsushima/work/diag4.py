#!/usr/bin/env python3
"""Nail the dialogue record layout + a clean total count.
Locate known strings, find the 16B record(s) pointing to them, dump raw+neighbors."""
import os, struct
HERE=os.path.dirname(os.path.abspath(__file__)); GAME=os.path.dirname(HERE)
EN=os.path.join(GAME,"extract","lang_english_text.xpps")
AR=os.path.join(GAME,"extract","lang_arabic_text.xpps")

d=open(EN,"rb").read()
base=struct.unpack_from("<I",d,0x28)[0]; trailer=struct.unpack_from("<I",d,0x2c)[0]; N=len(d)

def find_str_off(needle):
    """pool-relative offset of a NUL-preceded exact string."""
    b=needle.encode()
    pos=-1
    while True:
        pos=d.find(b"\x00"+b+b"\x00",pos+1)
        if pos<0: return None
        return (pos+1)-base   # pool-relative

for needle in ["Watch out!","I cannot be stopped!","Continue","New Game"]:
    off=find_str_off(needle)
    if off is None:
        print(f"{needle!r}: not found as isolated NUL-delimited string"); continue
    # find every 16B window whose second u64 low == off (off at bytes 8-11)  AND
    # whose bytes 12-15 == 0  -> the {u64 key, u64 off} layout
    hits_a=[]; hits_b=[]
    tgt=struct.pack("<Q",off)         # off as u64 at bytes 8
    tgt32=struct.pack("<I",off)       # off as u32
    p=0
    while True:
        p=d.find(tgt32,p+1)
        if p<0 or p>trailer: break
        # candidate record start if this u32 is the off field
        # layout A (alt): rec=[key(8)][off(4)][0(4)]  -> rec starts at p-8
        rsA=p-8
        if rsA>=0:
            k=struct.unpack_from("<Q",d,rsA)[0]; hi=struct.unpack_from("<I",d,p+4)[0]
            if hi==0: hits_a.append((rsA,k))
        # layout B (old): rec=[z(4)][A(4)][group(4)][off(4)] -> rec starts at p-12
        rsB=p-12
        if rsB>=0:
            z,A,g=struct.unpack_from("<III",d,rsB)
            hits_b.append((rsB,z,A,g))
    print(f"\n{needle!r} @pool+{off} (0x{off:x}):")
    print(f"  layoutA {{u64key,u64off}} hits: {len(hits_a)}")
    for rs,k in hits_a[:3]:
        print(f"     rec@0x{rs:x} raw={d[rs:rs+16].hex()} key={k:016x}")
    print(f"  layoutB {{z,A,grp,off}} hits: {len(hits_b)}")
    for rs,z,A,g in hits_b[:3]:
        print(f"     rec@0x{rs:x} raw={d[rs:rs+16].hex()} z={z} A={A:x} grp={g:x}")
