#!/usr/bin/env python3
"""
acs_forge.py — read-side parser for AC Shadows scimitar-v42 .forge archives.

VERIFIED layout (DataPC_AnimusRoom.forge, 2026-06-17 — the 24-byte record
cumulative-offset invariant `off[n+1] == off[n] + size[n]` held 102/102):

    Header @0:
        char[8] "scimitar"  ; u8 0 ; u32 version(=42)
        u64 @offset 13  -> index offset
    Index @indexOffset:
        u32 @ +0x0C  = resource COUNT
        u32 @ +0x28  = pointer to the RECORD ARRAY
    Record (24 bytes):
        u64 offset        ; on-disk offset of the resource blob
        u32 timestamp     ; unix mtime (~0x5825xxxx)
        u32 flags         ; resource flags/type (0,512,513,516,517,518,544,545,...)
        u32 size          ; on-disk size of the resource blob
        u32 nameHash      ; CRC/hash resource identifier

NOTE: each resource blob starts with its own per-resource descriptor (the
timestamp + flags are echoed inline), then the Oodle-Kraken payload (lead byte
0x8C — see acs_oodle.py). That inner sub-container is the next read layer to
crack to reach LocalizationPackage text; this tool exposes the TOC + raw blob
dump so that layer can be worked on real bytes. Read-only — never writes a forge.

    python acs_forge.py list  "<forge>" [--limit N] [--sort size|offset|hash]
    python acs_forge.py raw   "<forge>" <index> "<out.bin>"
    python acs_forge.py verify "<forge>"      # re-check the TOC invariant
"""
import sys
import os
import struct
import argparse

MAGIC = b"scimitar\x00"


def parse(path):
    with open(path, "rb") as f:
        head = f.read(64)
        if head[:9] != MAGIC:
            raise ValueError("not a scimitar forge")
        version = struct.unpack_from("<I", head, 9)[0]
        index_off = struct.unpack_from("<Q", head, 13)[0]
        f.seek(index_off)
        ihdr = f.read(0x30)
        count = struct.unpack_from("<I", ihdr, 0x0C)[0]
        arr = struct.unpack_from("<I", ihdr, 0x28)[0]
        f.seek(arr)
        raw = f.read(count * 24)
    recs = []
    for i in range(count):
        off, ts, fl, sz, h = struct.unpack_from("<QIIII", raw, i * 24)
        recs.append({"i": i, "offset": off, "ts": ts, "flags": fl, "size": sz, "hash": h})
    return {"version": version, "index_off": index_off, "count": count, "arr": arr, "recs": recs}


def invariant(recs):
    bad = sum(1 for i in range(len(recs) - 1)
              if recs[i]["offset"] + recs[i]["size"] != recs[i + 1]["offset"])
    return len(recs) - 1 - bad, len(recs) - 1


def cmd_list(path, limit, sort):
    info = parse(path)
    recs = info["recs"]
    if sort == "size":
        recs = sorted(recs, key=lambda r: -r["size"])
    elif sort == "hash":
        recs = sorted(recs, key=lambda r: r["hash"])
    good, total = invariant(info["recs"])
    print(f"{path}")
    print(f"  version={info['version']} count={info['count']} "
          f"index@0x{info['index_off']:x} array@0x{info['arr']:x}  invariant={good}/{total}")
    print(f"  {'idx':>4} {'offset':>11} {'size':>10} {'flags':>6}  nameHash")
    for r in recs[:limit]:
        print(f"  {r['i']:>4} 0x{r['offset']:>9x} 0x{r['size']:>8x} {r['flags']:>6}  0x{r['hash']:08x}")
    if limit < len(recs):
        print(f"  ... ({len(recs)-limit} more)")
    return 0


def cmd_raw(path, index, out):
    info = parse(path)
    if index < 0 or index >= info["count"]:
        print(f"index out of range 0..{info['count']-1}")
        return 1
    r = info["recs"][index]
    with open(path, "rb") as f:
        f.seek(r["offset"])
        blob = f.read(r["size"])
    with open(out, "wb") as g:
        g.write(blob)
    print(f"resource {index}: offset=0x{r['offset']:x} size=0x{r['size']:x} "
          f"hash=0x{r['hash']:08x} flags={r['flags']}")
    print(f"  first 32 bytes: {' '.join(f'{b:02x}' for b in blob[:32])}")
    print(f"  wrote {len(blob)} bytes -> {out}")
    return 0


def cmd_verify(path):
    info = parse(path)
    good, total = invariant(info["recs"])
    print(f"{os.path.basename(path)}: v{info['version']} count={info['count']} "
          f"invariant={good}/{total} {'OK' if good == total else 'MISMATCH'}")
    return 0 if good == total else 1


# --- resource sub-container (VERIFIED on AnimusRoom: 98/103 decode) ----------
# Each resource blob is a sequence of chunks. Chunk header = 0x1F bytes:
#   +0x00 u32 magic = 0x57FBAA33
#   +0x04 u32 const = 0x1004FA99
#   +0x13 u32 uncompressedSize   (data start - 0x0C)
#   +0x17 u32 compressedSize     (data start - 0x08)
#   +0x1B u32 checksum           (data start - 0x04)
#   +0x1F compressed (or stored, when comp==uncomp) payload of compressedSize
# Oodle-Kraken payload (lead 0x8C) decoded via acs_oodle.
CHUNK_MAGIC = 0x57FBAA33
CHUNK_HDR = 0x1F


def decode_resource(blob, oodle):
    """Walk chunks -> concatenated decompressed resource bytes. Returns
    (data, n_chunks, bytes_consumed)."""
    out = bytearray()
    pos = 0
    n = len(blob)
    chunks = 0
    while pos + CHUNK_HDR <= n:
        if struct.unpack_from("<I", blob, pos)[0] != CHUNK_MAGIC:
            break
        uncomp = struct.unpack_from("<I", blob, pos + 0x13)[0]
        comp = struct.unpack_from("<I", blob, pos + 0x17)[0]
        data = blob[pos + CHUNK_HDR: pos + CHUNK_HDR + comp]
        if len(data) < comp:
            raise ValueError("truncated chunk")
        out += data if comp == uncomp else oodle.decompress(data, uncomp)
        pos += CHUNK_HDR + comp
        chunks += 1
    return bytes(out), chunks, pos


def _read_blob(path, rec):
    with open(path, "rb") as f:
        f.seek(rec["offset"])
        return f.read(rec["size"])


def cmd_extract(path, index, out):
    from acs_oodle import Oodle
    info = parse(path)
    rec = info["recs"][index]
    blob = _read_blob(path, rec)
    data, ch, consumed = decode_resource(blob, Oodle())
    with open(out, "wb") as g:
        g.write(data)
    print(f"resource {index}: on-disk=0x{rec['size']:x} -> decompressed={len(data)} "
          f"({ch} chunks, consumed 0x{consumed:x}/0x{rec['size']:x})")
    print(f"  wrote {out}")
    return 0


def cmd_decode_stats(path, limit):
    from acs_oodle import Oodle
    info = parse(path)
    o = Oodle()
    ok = fail = total = 0
    recs = info["recs"][:limit] if limit else info["recs"]
    for r in recs:
        try:
            data, ch, consumed = decode_resource(_read_blob(path, r), o)
            if ch > 0 and consumed >= r["size"] - 16:
                ok += 1
                total += len(data)
            else:
                fail += 1
        except Exception:
            fail += 1
    print(f"{os.path.basename(path)}: decoded {ok}/{ok+fail} resources, "
          f"{total:,} bytes decompressed")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Read-only AC Shadows scimitar-v42 forge parser")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("forge"); p.add_argument("--limit", type=int, default=60)
    p.add_argument("--sort", choices=["index", "size", "hash", "offset"], default="index")
    r = sub.add_parser("raw"); r.add_argument("forge"); r.add_argument("index", type=int); r.add_argument("out")
    v = sub.add_parser("verify"); v.add_argument("forge")
    e = sub.add_parser("extract"); e.add_argument("forge"); e.add_argument("index", type=int); e.add_argument("out")
    ds = sub.add_parser("decode-stats"); ds.add_argument("forge"); ds.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "list":
        return cmd_list(a.forge, a.limit, a.sort)
    if a.cmd == "raw":
        return cmd_raw(a.forge, a.index, a.out)
    if a.cmd == "verify":
        return cmd_verify(a.forge)
    if a.cmd == "extract":
        return cmd_extract(a.forge, a.index, a.out)
    if a.cmd == "decode-stats":
        return cmd_decode_stats(a.forge, a.limit)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
