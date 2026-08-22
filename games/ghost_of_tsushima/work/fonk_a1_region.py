#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_region.py — locate the fOnk chunk bounds via the unique b139798e marker,
examine the low-entropy region before fOnk, and whole-file codepoint-ladder hunt."""
import os, struct, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(BIG, "rb").read()
N = len(raw)


def ent(b):
    if not b: return 0.0
    c = collections.Counter(b); n=len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

def hd(b, base=0, n=None):
    n = len(b) if n is None else n
    out=[]
    for i in range(0, min(n,len(b)), 16):
        c=b[i:i+16]
        out.append(f"  {base+i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   + "".join(chr(x) if 32<=x<127 else '.' for x in c))
    return "\n".join(out)

def findall(needle, lo=0, hi=None):
    hi = N if hi is None else hi
    out=[]; s=lo
    while True:
        i = raw.find(needle, s, hi)
        if i<0: break
        out.append(i); s=i+1
    return out


def main():
    # 1) bound the marker cluster precisely (b139798e = unique to fOnk region)
    D = bytes.fromhex("b139798e")
    occ = findall(D)
    print(f"== b139798e: {len(occ)} total; span 0x{occ[0]:x}..0x{occ[-1]:x} "
          f"(fOnk{occ[0]-FONK_OFF:+d} .. fOnk{occ[-1]-FONK_OFF:+d})")
    # fine entropy 1KB around the whole marker span +/- 4KB
    a, b = occ[0]-0x1000, occ[-1]+0x1000
    print(f"\n== fine entropy (512B) across marker span 0x{a:x}..0x{b:x} ==")
    for p in range(a, b, 512):
        h = ent(raw[p:p+512])
        m = " <fOnk" if p<=FONK_OFF<p+512 else ""
        print(f"   {p:x} (fOnk{p-FONK_OFF:+7d}) H={h:.2f} {'#'*int(h*3)}{m}")

    # 2) The low-entropy region ~28-31KB before fOnk: dump + interpret
    lo = FONK_OFF - 0x7c00
    print(f"\n== LOW-ENTROPY region @0x{lo:x} (fOnk-0x7c00) dump 0x180 ==")
    print(hd(raw[lo:lo+0x180], lo))

    # 3) whole-file codepoint ladder hunt (u16), scanning EVERYWHERE (coarse: strided)
    print("\n== whole-file u16 ascending-codepoint ladders (val in 0x20..0x6ff, run>=16) ==")
    hits = []
    for stride in (2, 4, 8, 16, 20, 24, 28, 32):
        for start0 in range(0, stride, 2):
            p = start0; prev=None; cnt=0; rs=None
            while p+2 <= N:
                v = struct.unpack_from("<H", raw, p)[0]
                ok = 0x20 <= v <= 0x6FF
                if ok and prev is not None and 0 < v-prev <= 6:
                    if rs is None: rs=p-stride; cnt=2
                    else: cnt+=1
                else:
                    if cnt>=16:
                        hits.append((stride, rs, cnt, prev))
                    rs=None; cnt=0
                prev = v if ok else None
                p += stride
            if cnt>=16: hits.append((stride, rs, cnt, prev))
    # dedupe/report
    hits.sort(key=lambda x:-x[2])
    for stride, rs, cnt, end in hits[:20]:
        print(f"   stride={stride} @0x{rs:x} run={cnt} end~{end:#x}  (fOnk{rs-FONK_OFF:+d})")
    if not hits:
        print("   NONE — codepoints are not stored as an ascending u16 ladder anywhere.")

    # 4) single-byte ASCII ladder (maybe cp stored as u8 for latin)
    print("\n== whole-file u8 ascending ladders (val 0x20..0x7e, run>=20) ==")
    for stride in (1,2,4,8,12,16,20,24,28,32):
        for start0 in range(0, stride):
            p=start0; prev=None; cnt=0; rs=None
            while p < N:
                v = raw[p]
                ok = 0x20 <= v <= 0x7e
                if ok and prev is not None and 0 < v-prev <= 4:
                    if rs is None: rs=p-stride; cnt=2
                    else: cnt+=1
                else:
                    if cnt>=20 and abs(rs-FONK_OFF) < 3_000_000:
                        print(f"   stride={stride} @0x{rs:x} run={cnt} end~{end:#x} (fOnk{rs-FONK_OFF:+d})")
                    rs=None; cnt=0
                prev = v if ok else None; end=v
                p += stride


if __name__ == "__main__":
    main()
