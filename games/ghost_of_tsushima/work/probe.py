#!/usr/bin/env python3
r"""probe.py — dump the exact DSAR + inner-PSARC structure of a GoT archive so we
can measure what an identity rebuild must reproduce (chunk size, comp types,
flags, header bytes, block-table encoding)."""
import os, sys, struct, hashlib, zlib

def dump(path):
    raw = open(path, "rb").read()
    print(f"== {os.path.basename(path)}  ({len(raw):,} B)  md5={hashlib.md5(raw).hexdigest()}")
    assert raw[:4] == b"DSAR", raw[:4]
    verMaj, verMin = struct.unpack_from("<HH", raw, 4)
    numEntries = struct.unpack_from("<I", raw, 8)[0]
    dataStart = struct.unpack_from("<I", raw, 12)[0]
    totalUncomp = struct.unpack_from("<Q", raw, 16)[0]
    pad = raw[0x18:0x20]
    print(f"DSAR v{verMaj}.{verMin} numEntries={numEntries} dataStart=0x{dataStart:x} "
          f"totalUncomp={totalUncomp:,} pad={pad!r}")
    # entries
    comptypes = {}
    reserved_set = set()
    entries = []
    for i in range(numEntries):
        base = 0x20 + i*32
        do, co = struct.unpack_from("<qq", raw, base)
        us, cs = struct.unpack_from("<ii", raw, base+16)
        ctype = raw[base+24]
        resv = raw[base+25:base+32]
        entries.append((do, co, us, cs, ctype, resv))
        comptypes[ctype] = comptypes.get(ctype, 0) + 1
        reserved_set.add(resv)
    print(f"entry compType histogram: {comptypes}")
    print(f"reserved 7-byte values seen: {[r.hex() for r in reserved_set]}")
    # chunk (uncompressed) size distribution
    uszs = [e[2] for e in entries]
    print(f"uncompSize distinct: {sorted(set(uszs))[:8]}{'...' if len(set(uszs))>8 else ''}  "
          f"max={max(uszs)}")
    print(f"first 3 entries: " + " | ".join(
        f"do={e[0]} co=0x{e[1]:x} us={e[2]} cs={e[3]} ct={e[4]}" for e in entries[:3]))
    print(f"last  entry     : do={entries[-1][0]} co=0x{entries[-1][1]:x} us={entries[-1][2]} cs={entries[-1][3]} ct={entries[-1][4]}")
    # verify contiguity of decompOffset
    exp = 0
    contig = True
    for do, co, us, cs, ct, r in entries:
        if do != exp:
            contig = False; break
        exp += us
    print(f"decompOffset contiguous & sums to totalUncomp: {contig and exp==totalUncomp}  (sum={exp:,})")
    # verify compOffset contiguity starting at dataStart
    coff_ok = True
    pos = dataStart
    for do, co, us, cs, ct, r in entries:
        if co != pos:
            coff_ok = False; break
        pos += cs
    print(f"compOffset contiguous from dataStart & ends at EOF: {coff_ok and pos==len(raw)}  (end=0x{pos:x} EOF=0x{len(raw):x})")
    # header raw hex
    print(f"header[0:0x20] = {raw[:0x20].hex()}")
    return raw, entries, dataStart, totalUncomp

if __name__ == "__main__":
    for p in sys.argv[1:]:
        dump(p); print()
