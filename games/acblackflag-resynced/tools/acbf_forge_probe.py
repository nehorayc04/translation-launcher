#!/usr/bin/env python3
"""
acbf_forge_probe.py -- read-only inspector for the 2025 Assassin's Creed IV:
Black Flag remaster's "scimitar" v50 .forge archives (Anvil engine).

Never writes to a forge. Tries the AC-Shadows-v42 header/TOC layout first
(same "scimitar\\x00"+u32 version + u64 indexOff@13 + 24-byte record array)
and reports whether the offset+size cumulative invariant holds, so we know
whether v50 reuses the v42 structure verbatim or needs field-layout changes.
"""
import sys
import os
import struct

MAGIC = b"scimitar\x00"


def try_v42_layout(path, dump_bytes=0):
    with open(path, "rb") as f:
        head = f.read(64)
        if head[:9] != MAGIC:
            return {"ok": False, "reason": "bad magic"}
        version = struct.unpack_from("<I", head, 9)[0]
        index_off = struct.unpack_from("<Q", head, 13)[0]
        size = os.fstat(f.fileno()).st_size
        if index_off <= 0 or index_off >= size:
            return {"ok": False, "reason": f"index_off {index_off} out of file bounds {size}", "version": version, "index_off": index_off}
        f.seek(index_off)
        ihdr = f.read(0x40)
        count = struct.unpack_from("<I", ihdr, 0x0C)[0]
        arr = struct.unpack_from("<I", ihdr, 0x28)[0]
        if count <= 0 or count > 5_000_000 or arr <= 0 or arr >= size:
            return {"ok": False, "reason": f"count={count} arr=0x{arr:x} look invalid",
                    "version": version, "index_off": index_off, "count": count, "arr": arr}
        f.seek(arr)
        need = count * 24
        if arr + need > size:
            return {"ok": False, "reason": f"record array runs past EOF (arr=0x{arr:x} need={need} size={size})",
                    "version": version, "index_off": index_off, "count": count, "arr": arr}
        raw = f.read(need)
    recs = []
    for i in range(count):
        off, ts, fl, sz, h = struct.unpack_from("<QIIII", raw, i * 24)
        recs.append({"i": i, "offset": off, "ts": ts, "flags": fl, "size": sz, "hash": h})
    bad = 0
    checked = 0
    for i in range(len(recs) - 1):
        if recs[i]["size"] == 0:
            continue
        checked += 1
        if recs[i]["offset"] + recs[i]["size"] != recs[i + 1]["offset"]:
            bad += 1
    return {
        "ok": True, "version": version, "index_off": index_off, "count": count,
        "arr": arr, "recs": recs, "invariant_bad": bad, "invariant_checked": checked,
    }


def main():
    path = sys.argv[1]
    info = try_v42_layout(path)
    print(f"file: {path}  size={os.path.getsize(path):,}")
    for k, v in info.items():
        if k == "recs":
            continue
        print(f"  {k}: {v}")
    if info.get("ok"):
        recs = info["recs"]
        print(f"  first 5 records:")
        for r in recs[:5]:
            print(f"    {r}")
        print(f"  last 5 records:")
        for r in recs[-5:]:
            print(f"    {r}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
