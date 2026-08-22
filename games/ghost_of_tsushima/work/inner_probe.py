#!/usr/bin/env python3
r"""Inspect the inner PSARC header/flags + reader sanity + the ct=254 anomaly."""
import os, sys, struct, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R

def inner_header(path):
    p = R.Psarc2(path)
    print(f"== {os.path.basename(path)}")
    print(f"  inner PSAR v{p.ver_major}.{p.ver_minor} comp={p.compression!r} numFiles={p.num_files} "
          f"tocSize=0x{p.total_toc_size:x} entrySize={p.toc_entry_size} blockSize=0x{p.block_size:x} flags=0x{p.archive_flags:x}")
    # full inner stream
    total = p.d.total_size
    inner = p.d.read(0, total)
    print(f"  inner stream: {len(inner):,} B  md5={hashlib.md5(inner).hexdigest()}")
    # read all files
    files = {}
    ok = True
    for e in p.files():
        try:
            files[e.path] = p.extract(e)
        except Exception as ex:
            ok = False
            print(f"  !! extract FAILED for {e.path}: {ex}")
    print(f"  extracted {len(files)} files, all-ok={ok}")
    p.d.f.close()
    return inner, files

def raw_254(path):
    """Look at the ct=254/cs=0 DSAR entry's on-disk bytes in gapack_misc_b."""
    raw = open(path, "rb").read()
    numEntries = struct.unpack_from("<I", raw, 8)[0]
    for i in range(numEntries):
        base = 0x20 + i*32
        do, co = struct.unpack_from("<qq", raw, base)
        us, cs = struct.unpack_from("<ii", raw, base+16)
        ct = raw[base+24]
        if ct == 254:
            nxt = struct.unpack_from("<q", raw, base+32+8)[0] if i+1 < numEntries else len(raw)
            print(f"  ct=254 entry #{i}: do={do} co=0x{co:x} us={us} cs={cs}; next co=0x{nxt:x} (gap={nxt-co})")
            print(f"    bytes@co: {raw[co:co+32].hex()}")

if __name__ == "__main__":
    for p in sys.argv[1:]:
        inner_header(p)
        if "misc_b" in p:
            raw_254(p)
        print()
