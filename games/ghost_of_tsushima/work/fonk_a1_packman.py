#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_packman.py — fully parse game.sprig.packman + correlate with the fOnk
offset in game.sprig.texmeshman. Goal: the fOnk chunk's {offset,size,flags}."""
import os, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
TMM  = os.path.join(EX, "game.sprig.texmeshman")
PKM  = os.path.join(EX, "game.sprig.packman")
FONK_OFF = 0x156BFF7
TMM_LEN  = 108445889


def main():
    pk = open(PKM, "rb").read()
    n = len(pk)
    print(f"packman {n:,} B")
    h0, h1 = struct.unpack_from("<QQ", pk, 0)
    cA, cB = struct.unpack_from("<II", pk, 16)
    print(f"hash0=0x{h0:016x} hash1=0x{h1:016x} countA={cA} countB={cB}")

    # Walk the u64 array at 0x18 while the high 48 bits stay constant.
    off = 0x18
    ids = []
    hi_const = None
    while off + 8 <= n:
        v = struct.unpack_from("<Q", pk, off)[0]
        hi = v >> 16
        if hi_const is None:
            hi_const = hi
        if hi != hi_const:
            break
        ids.append(v)
        off += 8
    print(f"\nu64 id-array: {len(ids)} entries, hi48=0x{hi_const:012x}, ends @0x{off:x}")
    print(f"  first ids low16: {[hex(x & 0xffff) for x in ids[:12]]}")
    print(f"  last  ids low16: {[hex(x & 0xffff) for x in ids[-6:]]}")
    lows = [x & 0xffff for x in ids]
    print(f"  low16 monotonic increasing: {all(lows[i] < lows[i+1] for i in range(len(lows)-1))}")
    diffs = collections.Counter(lows[i+1]-lows[i] for i in range(len(lows)-1))
    print(f"  low16 delta histogram (top): {diffs.most_common(6)}")

    # What follows the id array?
    rest = pk[off:]
    print(f"\nremaining after id-array: {len(rest)} B (from 0x{off:x} to 0x{n:x})")
    print("  hex[0:96]:")
    for i in range(0, min(96, len(rest)), 16):
        c = rest[i:i+16]
        print(f"    {off+i:06x}  {' '.join(f'{x:02x}' for x in c):<47}  "
              + "".join(chr(x) if 32 <= x < 127 else '.' for x in c))

    # Try to interpret 'rest' as records. Candidate widths: derive from countB.
    for w in (8, 12, 16, 20, 24):
        if len(rest) % w == 0:
            print(f"  rest divisible by {w}: {len(rest)//w} records")
    # If second section is (offset,size) pairs, look for a value near FONK_OFF / TMM_LEN.
    print(f"\n== search packman for u32/u64 near FONK_OFF=0x{FONK_OFF:x} or TMM_LEN=0x{TMM_LEN:x} ==")
    for wname, fmt, wid in (("u32", "<I", 4), ("u64", "<Q", 8)):
        hits32 = []
        for i in range(0, n - wid + 1):
            v = struct.unpack_from(fmt, pk, i)[0]
            if abs(v - FONK_OFF) < 0x4000 or (0 < v < TMM_LEN and abs(v - FONK_OFF) < 0x100):
                hits32.append((i, v))
        print(f"  {wname} within 0x4000 of FONK_OFF: {len(hits32)}")
        for i, v in hits32[:20]:
            print(f"    @0x{i:x}: {v:#x} (fOnk{v-FONK_OFF:+d})")

    # Also: does the id-array count (3621) match number of chunks? And is countB a
    # different table? Dump around the boundary and the tail.
    print(f"\n== tail of packman (last 96 B) ==")
    for i in range(max(0, n-96), n, 16):
        c = pk[i:i+16]
        print(f"    {i:06x}  {' '.join(f'{x:02x}' for x in c):<47}  "
              + "".join(chr(x) if 32 <= x < 127 else '.' for x in c))


if __name__ == "__main__":
    main()
