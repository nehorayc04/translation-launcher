#!/usr/bin/env python3
"""
acs_oasis.py — extract AC Shadows localized strings keyed by Oasis line-ID.

AC Shadows does NOT store text as an ATK-style fragment LocalizationPackage
(the class hash 0x6E37B1AF is absent from the shipped forges). Instead each
localized string is a field record inside a serialized ScimitarClass:

    [ lineID  u64 ][ 0xFADE9F44 u32 ][ 00 ][ convID u64 ][ 0000 u32 ]
    [ charLen u32 ][ UTF-16LE text, charLen code units ]

`0xFADE9F44` (bytes 44 9F DE FA) is the localized-string field-type tag.
The u64 immediately BEFORE the tag is the unique Oasis line-ID (the key the
per-language packages share); the u64 after is a shared conversation/group id.
Verified on DataPC_boot.forge idx 36626 (10/10 lines, unique lineIDs).

    python acs_oasis.py scan   "<forge>" [--min N] [--max-size B] [--out J]
        decompress every resource, count FADE9F44 records, log dense ones
    python acs_oasis.py dump    "<forge>" <index> <out.json>
        extract {lineID: text} from one resource
    python acs_oasis.py extract "<forge>" --out <out.json> [--max-size B]
        extract {lineID: text} from EVERY resource -> merged JSON
"""
import sys
import os
import struct
import json
import argparse

TAG = struct.pack("<I", 0xFADE9F44)


def _tools():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F
    import acs_cfd as C
    return F, C


def _decompress(forge, rec, oodle):
    import acs_cfd as C
    with open(forge, "rb") as f:
        f.seek(rec["offset"]); blob = f.read(rec["size"])
    cfds, _ = C.decode_resource(blob, oodle)
    return b"".join(d for d, _ in cfds)


def extract_strings(data):
    """Return {lineID(int): text} for every FADE9F44 record in `data`."""
    out = {}
    n = len(data)
    pos = 0
    while True:
        m = data.find(TAG, pos)
        if m < 0:
            break
        pos = m + 4
        if m < 8 or m + 21 > n:
            continue
        try:
            line_id = struct.unpack_from("<Q", data, m - 8)[0]
            clen = struct.unpack_from("<I", data, m + 17)[0]
            if clen <= 0 or clen > 60000 or m + 21 + clen * 2 > n:
                continue
            txt = data[m + 21:m + 21 + clen * 2].decode("utf-16-le", "replace")
            out[line_id] = txt
        except Exception:
            continue
    return out


def _oodle():
    F, C = _tools()
    return C._oodle()


def cmd_scan(forge, min_count, max_size, out):
    F, C = _tools()
    o = _oodle()
    info = F.parse(forge)
    recs = info["recs"]
    total_records = 0
    dense = []
    base = os.path.basename(forge)
    for n, r in enumerate(recs):
        if n % 5000 == 0:
            print(f"  {base}: {n}/{len(recs)} probed, {len(dense)} dense, "
                  f"{total_records:,} records so far", flush=True)
            if out:
                json.dump({"forge": forge, "probed": n, "dense": dense,
                           "total_records": total_records},
                          open(out, "w"), indent=1)
        if max_size and r["size"] > max_size:
            continue
        if r["size"] < 64:
            continue
        try:
            data = _decompress(forge, r, o)
        except Exception:
            continue
        c = data.count(TAG)
        if c:
            total_records += c
            if c >= min_count:
                dense.append({"i": r["i"], "count": c, "size": r["size"],
                              "decomp": len(data), "flags": r["flags"],
                              "hash": r["hash"]})
    dense.sort(key=lambda d: -d["count"])
    print(f"DONE {base}: {len(dense)} resources with >={min_count} records, "
          f"{total_records:,} total records", flush=True)
    for d in dense[:40]:
        print(f"  idx {d['i']:>7} count {d['count']:>6} size 0x{d['size']:x} "
              f"flags {d['flags']} hash 0x{d['hash']:08x}")
    if out:
        json.dump({"forge": forge, "probed": len(recs), "dense": dense,
                   "total_records": total_records}, open(out, "w"), indent=1)
        print(f"  -> {out}")
    return 0


def cmd_dump(forge, index, out):
    F, C = _tools()
    o = _oodle()
    info = F.parse(forge)
    data = _decompress(forge, info["recs"][index], o)
    strings = extract_strings(data)
    json.dump({str(k): v for k, v in strings.items()},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"resource {index}: {len(strings)} strings -> {out}")
    return 0


def cmd_extract(forge, out, max_size):
    F, C = _tools()
    o = _oodle()
    info = F.parse(forge)
    merged = {}
    base = os.path.basename(forge)
    for n, r in enumerate(info["recs"]):
        if n % 5000 == 0:
            print(f"  {base}: {n}/{info['count']} probed, {len(merged):,} strings",
                  flush=True)
        if max_size and r["size"] > max_size:
            continue
        if r["size"] < 64:
            continue
        try:
            data = _decompress(forge, r, o)
        except Exception:
            continue
        if TAG not in data:
            continue
        for k, v in extract_strings(data).items():
            merged[k] = v
    json.dump({str(k): v for k, v in merged.items()},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"DONE {base}: {len(merged):,} unique strings -> {out}", flush=True)
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="AC Shadows Oasis string extractor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("forge")
    s.add_argument("--min", type=int, default=30); s.add_argument("--max-size", type=int, default=15_000_000)
    s.add_argument("--out", default=None)
    d = sub.add_parser("dump"); d.add_argument("forge"); d.add_argument("index", type=int); d.add_argument("out")
    e = sub.add_parser("extract"); e.add_argument("forge"); e.add_argument("--out", required=True)
    e.add_argument("--max-size", type=int, default=15_000_000)
    a = ap.parse_args()
    if a.cmd == "scan":
        return cmd_scan(a.forge, a.min, a.max_size, a.out)
    if a.cmd == "dump":
        return cmd_dump(a.forge, a.index, a.out)
    if a.cmd == "extract":
        return cmd_extract(a.forge, a.out, a.max_size)


if __name__ == "__main__":
    sys.exit(main())
