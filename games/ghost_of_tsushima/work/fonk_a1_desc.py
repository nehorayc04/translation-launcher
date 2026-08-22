#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_desc.py — read the NAMS descriptor that points at fOnk (@0x5d8060) to get
the chunk size + name; find the fundamental record period via multi-lag autocorr."""
import os, struct

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(BIG, "rb").read()
N = len(raw)


def hd(b, base=0, n=None):
    n=len(b) if n is None else n; out=[]
    for i in range(0,min(n,len(b)),16):
        c=b[i:i+16]
        out.append(f"  {base+i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   +"".join(chr(x) if 32<=x<127 else '.' for x in c))
    return "\n".join(out)


def main():
    # 1) The descriptor at 0x5d8060 = u32 0x156bff6. Dump around it to read the record.
    D = 0x5d8060
    print(f"== descriptor region @0x{D:x} (holds ptr fOnk-1) ==")
    print(hd(raw[D-0x60:D+0x80], D-0x60))
    # look for a nearby name (ascii run) and a size (u32 == chunk length)
    ctx = raw[D-0x100:D+0x100]
    # find ascii names
    import re
    for m in re.finditer(rb"[ -~]{5,}", ctx):
        print(f"   ascii @0x{D-0x100+m.start():x}: {m.group()!r}")

    # 2) ALL descriptors (aligned u32 == a value in [fOnk-0x40, fOnk+0x40]) and the
    #    surrounding u32s (to guess size layout). Also collect the exact-fOnk ones.
    print("\n== aligned u32 pointers hitting [fOnk-64,fOnk+64] + neighbours ==")
    import numpy as np
    arr = np.frombuffer(raw[:N//4*4], dtype="<u4")
    idx = np.nonzero((arr >= FONK_OFF-64) & (arr <= FONK_OFF+64))[0]
    for i in idx[:12]:
        off=i*4
        around = struct.unpack_from("<8I", raw, max(0,off-16))
        print(f"   @0x{off:x} ptr={int(arr[i]):#x}(fOnk{int(arr[i])-FONK_OFF:+d})  "
              f"u32[-4..+4]={[hex(x) for x in around]}")

    # 3) fundamental period: autocorrelation match-rate at many lags on fOnk..+30KB
    print("\n== byte match-rate vs lag (find fundamental record size) ==")
    a = raw[FONK_OFF:FONK_OFF+30000]
    def mr(lag):
        m=0
        for i in range(0, len(a)-lag, 3):  # sample every 3 for speed
            if a[i]==a[i+lag]: m+=1
        return m / (len(a)-lag) * 3
    lags = [2,4,8,12,14,16,20,24,28,32,48,49,56,64,98,112,196,343,392,686,784,
            1000,1372,2744,5488,5487,5489,10976]
    for L in lags:
        r = mr(L)
        star = " <== PEAK" if r > 0.05 else ""
        print(f"   lag {L:6d}: {r:.4f}{star}")

    # 4) Also: does the whole file have this descriptor for OTHER known resources so we
    #    can learn the record layout? Show the u32 just AFTER the pointer (candidate size).
    print("\n== candidate size fields near each fOnk-region pointer ==")
    idx2 = np.nonzero((arr >= FONK_OFF-0x2000) & (arr <= FONK_OFF+0x200))[0]
    for i in idx2[:8]:
        off=i*4
        # print a few u32 after the pointer
        post = struct.unpack_from("<6I", raw, off+4)
        print(f"   ptr@0x{off:x}={int(arr[i]):#x}: post u32 {[hex(x) for x in post]}")


if __name__ == "__main__":
    main()
