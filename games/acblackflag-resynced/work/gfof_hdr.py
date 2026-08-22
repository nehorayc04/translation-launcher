# -*- coding: utf-8 -*-
"""Dump the GFOF header of every atlas + walk the record chain to find the
TRUE record count, then compare against every header field."""
import os, struct, collections

ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
REC = 36
FMT = "<7f2I"

def chain_len(data, tbl, cap=200000):
    """Walk records while bmpOffset[i]+w*h == bmpOffset[i+1] and fields sane."""
    n = 0
    prev = None
    while tbl + (n + 1) * REC <= len(data):
        adv, x0, y0, x1, y1, w, h, bo, cp = struct.unpack_from(FMT, data, tbl + n * REC)
        if not (0 <= cp <= 0x10FFFF): break
        if not (w == int(w) and h == int(h) and 0 <= w <= 1024 and 0 <= h <= 1024): break
        if prev is not None and prev[0] + prev[1] * prev[2] != bo: break
        prev = (bo, int(w), int(h))
        n += 1
        if n > cap: break
    return n, (prev[0] + prev[1] * prev[2]) if prev else 0

rows = []
for fn in sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin")):
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    tbl = g + 0x48
    n, reach = chain_len(data, tbl)
    hdr = [struct.unpack_from("<I", data, g + 4 + 4 * i)[0] for i in range(17)]
    hdrf = [struct.unpack_from("<f", data, g + 4 + 4 * i)[0] for i in range(17)]
    rows.append((fn, len(data), g, n, reach, hdr, hdrf))

print(f"{'file':26s} {'size':>9} {'GFOF':>6} {'chainN':>7} {'reach':>10} {'tblEnd':>8} {'size-reach':>11}")
for fn, sz, g, n, reach, hdr, hdrf in rows:
    te = g + 0x48 + n * REC
    print(f"{fn:26s} {sz:>9} 0x{g:04x} {n:>7} {reach:>10} 0x{te:06x} {sz-reach:>11}")

print()
print("header dwords (GFOF+4 .. GFOF+0x44), u32 / f32 where plausible")
hdrnames = [f"+0x{4+4*i:02x}" for i in range(17)]
print(f"{'field':>7} " + " ".join(f"{r[0][:5]:>11}" for r in rows))
for i in range(17):
    vals = []
    for r in rows:
        u, f = r[5][i], r[6][i]
        s = str(u) if u < 1 << 28 else f"{f:.4g}"
        vals.append(s)
    print(f"{hdrnames[i]:>7} " + " ".join(f"{v:>11}" for v in vals))

print()
print("match test: which header field equals chainN?")
for i in range(17):
    if all(r[5][i] == r[3] for r in rows):
        print(f"  ** GFOF{hdrnames[i]} == chainN for ALL files **")
    elif sum(r[5][i] == r[3] for r in rows) >= 2:
        print(f"  ~ GFOF{hdrnames[i]} matches {sum(r[5][i]==r[3] for r in rows)}/{len(rows)}")
