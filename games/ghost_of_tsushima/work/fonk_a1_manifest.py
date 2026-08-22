#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_manifest.py — harvest real NAMS resource entries {offset,name} to derive
the fOnk chunk's exact size, and probe where the 16-byte/5488 period begins."""
import os, struct, re

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
BIG  = os.path.join(EX, "game.sprig.texmeshman")
FONK_OFF = 0x156BFF7
raw = open(BIG, "rb").read()
N = len(raw)


def deinterleave_name(b):
    """names use [0xff][8 bytes] framing sometimes; strip stray 0xff sentinels."""
    return bytes(x for x in b if x != 0xff)


def main():
    # The 0x1411a4 entry: offset@p, u32 @p+4, u32 namelen @p+8, name @p+12.
    # Verify layout by dumping it fully.
    p = 0x1411a4
    print("== entry @0x1411a4 (offset 0x156a140, fOnk-7863) full ==")
    off, a, nl = struct.unpack_from("<III", raw, p)
    print(f"   offset={off:#x} field1={a} namelen={nl}")
    name = raw[p+12:p+12+nl]
    print(f"   name raw={name!r}")
    print(f"   name clean={deinterleave_name(name)!r}")
    # dump around
    print("   hexdump:")
    for i in range(p-8, p+12+nl+24, 16):
        c = raw[i:i+16]
        print(f"     {i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
              + "".join(chr(x) if 32<=x<127 else '.' for x in c))

    # Harvest ALL entries with the pattern: u32 offset (plausible data ptr in
    # [0x100000, N]) then a namelen 3..80 then printable-ish name, near-ish.
    # We look across the whole file but keep only well-formed ones, then sort by offset.
    print("\n== harvesting well-formed {offset,namelen,name} entries near fOnk ==")
    ents = []
    # scan for the specific structure: offset in [FONK-0x20000, FONK+0x20000],
    # followed at +8 by a small namelen, at +12 by mostly-printable bytes.
    lo, hi = FONK_OFF-0x20000, FONK_OFF+0x40000
    i = 0
    while i < N-16:
        off = struct.unpack_from("<I", raw, i)[0]
        if lo <= off <= hi:
            nl = struct.unpack_from("<I", raw, i+8)[0]
            if 3 <= nl <= 80:
                nm = raw[i+12:i+12+nl]
                printable = sum(1 for x in nm if 32<=x<127 or x==0xff)
                if printable >= nl*0.8:
                    ents.append((off, i, nl, deinterleave_name(nm)))
        i += 1
    ents.sort()
    # dedupe by offset
    seen=set(); uniq=[]
    for e in ents:
        if e[0] in seen: continue
        seen.add(e[0]); uniq.append(e)
    print(f"   {len(uniq)} unique-offset well-formed entries")
    # find the ones bracketing FONK_OFF
    for k,(off,at,nl,nm) in enumerate(uniq):
        mark = ""
        if k+1 < len(uniq):
            size = uniq[k+1][0]-off
        else:
            size = None
        if FONK_OFF-0x3000 <= off <= FONK_OFF+0x3000:
            print(f"   off={off:#x}(fOnk{off-FONK_OFF:+d}) entry@{at:#x} size~{size} name={nm[:40]!r}")

    # Probe: where does the 16-byte / 5488 period begin? match-rate at lag 5488 for
    # sliding 4KB windows from fOnk-8KB to fOnk+16KB.
    print("\n== lag-5488 match-rate for 4KB windows (find periodic region start) ==")
    def mr(base, lag, span=4096):
        a = raw[base:base+span+lag]
        m=sum(1 for i in range(0,span,2) if a[i]==a[i+lag])
        return m/(span//2)
    for d in range(-8192, 20000, 2048):
        print(f"   fOnk{d:+6d} (0x{FONK_OFF+d:x}): lag5488={mr(FONK_OFF+d,5488):.3f}")

    # 16-byte aligned dump right after fOnk (see the record structure)
    print("\n== 16-byte rows fOnk+16 .. fOnk+16+16*10 ==")
    base = FONK_OFF+16
    for r in range(10):
        c = raw[base+r*16:base+r*16+16]
        u16 = struct.unpack_from("<8H", c, 0)
        print(f"   {base+r*16:08x}  {c.hex()}  u16={[hex(x) for x in u16]}")


if __name__ == "__main__":
    main()
