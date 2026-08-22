#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_scan.py — Attempt #1 STEP 1: locate & characterize the fOnk chunk.

Runs against the REAL extracted files (analysis only, no game-file writes):
  extract/game.sprig.texmeshman  (108 MB, container magic NAMS)
  extract/game.sprig.packman     (68 KB, index)

Prints: fOnk tag context, packman header + record scan, entropy map around fOnk,
and searches for the "b1 39 79 8e" delimiter pattern occurrences."""
import os, sys, struct, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EX   = os.path.join(HERE, "..", "extract")
TMM  = os.path.join(EX, "game.sprig.texmeshman")
PKM  = os.path.join(EX, "game.sprig.packman")

FONK_OFF = 0x156BFF7   # given: the ONLY fOnk in shipped data
DELIM    = bytes.fromhex("b139798e")


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n) * math.log2(v/n) for v in c.values())


def hexdump(b, base=0, n=None):
    n = len(b) if n is None else n
    out = []
    for i in range(0, min(n, len(b)), 16):
        chunk = b[i:i+16]
        hx = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        out.append(f"  {base+i:08x}  {hx:<47}  {asc}")
    return "\n".join(out)


def main():
    raw = open(TMM, "rb").read()
    print(f"== texmeshman: {len(raw):,} B  magic={raw[:4]!r}")
    print(f"   header[0:64]:")
    print(hexdump(raw[:64], 0))

    # confirm fOnk offset
    at = raw[FONK_OFF:FONK_OFF+4]
    print(f"\n== fOnk tag @0x{FONK_OFF:x}: {at!r}")
    assert at == b"fOnk", at
    # all fOnk occurrences
    occ = []
    s = 0
    while True:
        i = raw.find(b"fOnk", s)
        if i < 0:
            break
        occ.append(i)
        s = i + 1
    print(f"   all fOnk occurrences: {[hex(x) for x in occ]}")

    print(f"\n== context around fOnk (0x{FONK_OFF-64:x} .. 0x{FONK_OFF+128:x}):")
    print(hexdump(raw[FONK_OFF-64:FONK_OFF+128], FONK_OFF-64))

    # entropy sweep after fOnk
    print(f"\n== entropy sweep (1 KB windows) from fOnk to +32 KB:")
    for k in range(0, 32*1024, 1024):
        w = raw[FONK_OFF+k:FONK_OFF+k+1024]
        print(f"   +0x{k:05x}: H={entropy(w):.3f}")

    # entropy BEFORE fOnk (to find where the high-entropy region starts)
    print(f"\n== entropy sweep (1 KB windows) BEFORE fOnk, -32 KB .. fOnk:")
    for k in range(-32*1024, 0, 1024):
        w = raw[FONK_OFF+k:FONK_OFF+k+1024]
        print(f"   {k:+07x}: H={entropy(w):.3f}")

    # delimiter occurrences near fOnk (± 256 KB)
    lo, hi = max(0, FONK_OFF-256*1024), min(len(raw), FONK_OFF+256*1024)
    region = raw[lo:hi]
    dpos = []
    s = 0
    while True:
        i = region.find(DELIM, s)
        if i < 0:
            break
        dpos.append(lo+i)
        s = i + 1
    print(f"\n== 'b1 39 79 8e' delimiter in ±256KB of fOnk: {len(dpos)} hits")
    for p in dpos[:40]:
        print(f"   0x{p:08x}  (fOnk{p-FONK_OFF:+d})   ctx: {raw[p-4:p+12].hex()}")

    # global count of delimiter
    gs = 0; gcount = 0
    while True:
        i = raw.find(DELIM, gs)
        if i < 0:
            break
        gcount += 1
        gs = i + 1
    print(f"   GLOBAL delimiter count in texmeshman: {gcount}")

    # ---- packman ----
    print("\n" + "="*70)
    pk = open(PKM, "rb").read()
    print(f"== packman: {len(pk):,} B")
    print(hexdump(pk[:128], 0))
    # header per the task hint: two u64 hashes, then u32 3621, u32 3614
    h0, h1 = struct.unpack_from("<QQ", pk, 0)
    a, b = struct.unpack_from("<II", pk, 16)
    print(f"\n   u64[0]=0x{h0:016x}  u64[1]=0x{h1:016x}")
    print(f"   u32@16={a} ({a:#x})   u32@20={b} ({b:#x})")
    print(f"   more u32 @24: {struct.unpack_from('<8I', pk, 24)}")


if __name__ == "__main__":
    main()
