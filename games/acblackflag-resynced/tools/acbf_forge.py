#!/usr/bin/env python3
"""
acbf_forge.py -- read-side parser for AC Black Flag Resynced scimitar-v50 forges.

CRACKED v50 layout (2026-07-10, invariant off[n+1]==off[n]+size[n] held
95/95 on DataPC_RED_TitleScreen.forge and re-verified on the big forges):

    Header @0:
        char[8] "scimitar" ; u8 0 ; u32 version(=50)
        u32 @13  = 0x41a   (CONSTANT: pointer to the manifest descriptor)
    Manifest descriptor @0x41a:
        u32  count          # number of resource records
        u64  tocOffset      # -> the record array (u64: boot.forge's TOC is >4GB in)
        u32  0
        u64  0xFFFFFFFFFFFFFFFF   (sentinel)
    TOC @tocOffset:
        count * 24-byte records, each  <QIIII>:
            u64 offset      # on-disk offset of the resource blob
            u32 timestamp
            u32 flags       # resource flags/type
            u32 size        # on-disk size of the resource blob
            u32 nameHash    # resource identifier

    (v42 stored count/arr via a u64 index_off @13; v50 hoists them into a
     fixed 0x41a manifest descriptor.  Record layout itself is unchanged.)

Resource blob -> 0x57FBAA33 Oodle-Kraken chunks (see acbf_loc.py). Read-only.

    python acbf_forge.py list   "<forge>" [--limit N] [--sort size|hash|offset]
    python acbf_forge.py verify "<forge>"
    python acbf_forge.py raw    "<forge>" <index> "<out.bin>"
    python acbf_forge.py hash   "<forge>" <nameHash-hex>   # find record by hash
"""
import sys
import os
import struct
import argparse

MAGIC = b"scimitar\x00"
DESC_OFF = 0x41a
REC = 24


def parse(path):
    with open(path, "rb") as f:
        head = f.read(0x41a + 24)
        if head[:9] != MAGIC:
            raise ValueError("not a scimitar forge")
        version = struct.unpack_from("<I", head, 9)[0]
        desc_ptr = struct.unpack_from("<I", head, 13)[0]
        count = struct.unpack_from("<I", head, desc_ptr)[0]
        toc = struct.unpack_from("<Q", head, desc_ptr + 4)[0]   # u64: 25GB boot TOC is >4GB in
        f.seek(toc)
        raw = f.read(count * REC)
    recs = []
    for i in range(count):
        off, ts, fl, sz, h = struct.unpack_from("<QIIII", raw, i * REC)
        recs.append({"i": i, "offset": off, "ts": ts, "flags": fl, "size": sz, "hash": h})
    return {"version": version, "desc_ptr": desc_ptr, "count": count, "toc": toc, "recs": recs}


def invariant(recs):
    bad = sum(1 for i in range(len(recs) - 1)
              if recs[i]["size"] and recs[i]["offset"] + recs[i]["size"] != recs[i + 1]["offset"])
    chk = sum(1 for i in range(len(recs) - 1) if recs[i]["size"])
    return chk - bad, chk


def cmd_list(path, limit, sort):
    info = parse(path)
    recs = info["recs"]
    if sort == "size":
        recs = sorted(recs, key=lambda r: -r["size"])
    elif sort == "hash":
        recs = sorted(recs, key=lambda r: r["hash"])
    elif sort == "offset":
        recs = sorted(recs, key=lambda r: r["offset"])
    good, total = invariant(info["recs"])
    print(f"{os.path.basename(path)}  v{info['version']} count={info['count']} "
          f"desc@0x{info['desc_ptr']:x} toc@0x{info['toc']:x}  invariant={good}/{total}")
    print(f"  {'idx':>5} {'offset':>12} {'size':>11} {'flags':>6}  nameHash")
    for r in recs[:limit]:
        print(f"  {r['i']:>5} 0x{r['offset']:>10x} 0x{r['size']:>9x} {r['flags']:>6}  0x{r['hash']:08x}")
    if limit < len(recs):
        print(f"  ... ({len(recs)-limit} more)")
    return 0


def cmd_verify(path):
    info = parse(path)
    good, total = invariant(info["recs"])
    print(f"{os.path.basename(path)}: v{info['version']} count={info['count']} "
          f"invariant={good}/{total} {'OK' if good == total else 'MISMATCH'}")
    return 0 if good == total else 1


def cmd_raw(path, index, out):
    info = parse(path)
    r = info["recs"][index]
    with open(path, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    open(out, "wb").write(blob)
    print(f"resource {index}: off=0x{r['offset']:x} size=0x{r['size']:x} "
          f"flags={r['flags']} hash=0x{r['hash']:08x}")
    print(f"  first 32: {' '.join(f'{b:02x}' for b in blob[:32])}")
    print(f"  -> {out}")
    return 0


def cmd_hash(path, hexhash):
    want = int(hexhash, 16)
    info = parse(path)
    hits = [r for r in info["recs"] if r["hash"] == want]
    print(f"{os.path.basename(path)}: {len(hits)} record(s) with hash 0x{want:08x}")
    for r in hits:
        print(f"  idx {r['i']} off=0x{r['offset']:x} size=0x{r['size']:x} flags={r['flags']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("forge"); p.add_argument("--limit", type=int, default=60)
    p.add_argument("--sort", choices=["index", "size", "hash", "offset"], default="index")
    v = sub.add_parser("verify"); v.add_argument("forge")
    r = sub.add_parser("raw"); r.add_argument("forge"); r.add_argument("index", type=int); r.add_argument("out")
    h = sub.add_parser("hash"); h.add_argument("forge"); h.add_argument("hexhash")
    a = ap.parse_args()
    if a.cmd == "list":
        return cmd_list(a.forge, a.limit, a.sort)
    if a.cmd == "verify":
        return cmd_verify(a.forge)
    if a.cmd == "raw":
        return cmd_raw(a.forge, a.index, a.out)
    if a.cmd == "hash":
        return cmd_hash(a.forge, a.hexhash)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
