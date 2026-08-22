#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_deep.py — decisive structural probe of the fOnk region."""
import os, struct, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(BIG, "rb").read()
N = len(raw)


def hd(b, base=0, n=None):
    n = len(b) if n is None else n
    out=[]
    for i in range(0, min(n,len(b)), 16):
        c=b[i:i+16]
        out.append(f"  {base+i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   + "".join(chr(x) if 32<=x<127 else '.' for x in c))
    return "\n".join(out)

def findall(needle, lo=0, hi=None):
    hi=N if hi is None else hi; out=[]; s=lo
    while True:
        i=raw.find(needle,s,hi)
        if i<0: break
        out.append(i); s=i+1
    return out


def main():
    # 1) search whole file for a u32/u64 pointing at/near fOnk (=> NAMS descriptor)
    print("== search whole texmeshman for u32 LE in [fOnk-0x2000, fOnk+0x200] ==")
    import numpy as np
    arr = np.frombuffer(raw[:len(raw)//4*4], dtype="<u4")
    lo, hi = FONK_OFF-0x2000, FONK_OFF+0x200
    idx = np.nonzero((arr >= lo) & (arr <= hi))[0]
    print(f"   {len(idx)} u32-aligned hits")
    for i in idx[:30]:
        off = i*4; v = int(arr[i])
        print(f"    @0x{off:x}: {v:#x} (fOnk{v-FONK_OFF:+d})  ctx {raw[off-4:off+12].hex()}")
    # unaligned u32 search near — also try u64
    print("\n== search whole file (byte-aligned) for u32==fOnk-ish (unaligned) ==")
    tgt_lo, tgt_hi = FONK_OFF-0x40, FONK_OFF+0x8
    hits=0
    for i in range(0, N-4, 1):
        v = int.from_bytes(raw[i:i+4], "little")
        if tgt_lo <= v <= tgt_hi and abs(i-FONK_OFF) > 0x100:
            print(f"    @0x{i:x}: {v:#x} (fOnk{v-FONK_OFF:+d}) ctx {raw[i-6:i+10].hex()}")
            hits+=1
            if hits>=20: break
    if hits==0: print("   none (chunk not referenced by absolute offset near fOnk value)")

    # 2) clean dump fOnk .. fOnk+320
    print(f"\n== fOnk .. +320 ==")
    print(hd(raw[FONK_OFF:FONK_OFF+320], FONK_OFF))

    # 3) One full 5488 block: rRxF@0x156d7b9 .. next. Dump the block start (the
    #    MJwN@11-before) and the transition.
    rr = findall(b"rRxF")
    print(f"\n== 5488-period anchor: bytes around rRxF@0x{rr[1]:x} (block boundary?) ==")
    print(hd(raw[rr[1]-32:rr[1]+64], rr[1]-32))
    print(f"   delta rRxF[2]-rRxF[1] = {rr[2]-rr[1]}")

    # 4) after each b139798e marker: what codepoint-like value follows?
    print("\n== bytes right AFTER each b139798e marker (glyph header?) ==")
    D = bytes.fromhex("b139798e")
    for m in findall(D)[:16]:
        after = raw[m+4:m+4+12]
        u16s = struct.unpack_from("<6H", after, 0)
        print(f"   @0x{m:x}(fOnk{m-FONK_OFF:+d}) after={after.hex()} u16={[hex(x) for x in u16s]}")

    # 5) float32 / float16 range test on fOnk+64..+4096 (glyph coord data?)
    seg = raw[FONK_OFF+64:FONK_OFF+64+4096]
    f32 = np.frombuffer(seg, dtype="<f4")
    finite = f32[np.isfinite(f32)]
    small = finite[(np.abs(finite) < 1e4)]
    print(f"\n== float32 test fOnk+64..+4160: {len(f32)} vals, {len(small)} finite&|v|<1e4 "
          f"({100*len(small)/len(f32):.1f}%)")
    if len(small): print(f"   small-f32 sample: {[round(float(x),3) for x in small[:12]]}")
    f16 = np.frombuffer(seg, dtype="<f2")
    fin16 = f16[np.isfinite(f16)]
    sm16 = fin16[(np.abs(fin16) < 1e3)]
    print(f"== float16 test: {len(f16)} vals, {len(sm16)} finite&|v|<1e3 ({100*len(sm16)/len(f16):.1f}%)")
    if len(sm16): print(f"   small-f16 sample: {[round(float(x),3) for x in sm16[:16]]}")

    # 6) Is the WHOLE font-region self-similar? autocorrelation-ish: count matching
    #    bytes at lag 5488 vs random lag.
    a = raw[FONK_OFF:FONK_OFF+5488*5]
    def matchrate(lag):
        return sum(1 for i in range(len(a)-lag) if a[i]==a[i+lag]) / (len(a)-lag)
    print(f"\n== byte match-rate at lag 5488 = {matchrate(5488):.4f}; lag 5489 = {matchrate(5489):.4f}; "
          f"lag 1000 = {matchrate(1000):.4f} (baseline ~1/256=0.0039)")


if __name__ == "__main__":
    main()
