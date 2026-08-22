#!/usr/bin/env python3
r"""
tlou_loc.py — codec for The Last of Us Part I "text2" localization files
(`<lang>.common`, `<lang>.subtitles`, `<lang>.subtitles-systemic`, `sid-lookup`),
the Naughty Dog "version 2" string table. Pure-Python, self-testing round-trip.

Layout (little-endian):
    uint32  count
    count * { uint64 stringId ; uint64 blobOffset }     # 16 bytes/record
    blob:   UTF-8, each string NUL-terminated at (blob_start + blobOffset)
            where blob_start = 4 + count*16

* stringId (SID) is the SAME across every language file -> map EN->HE by SID.
* Multiple records may share one blobOffset (deduped identical strings).
* Encoding is UTF-8; Hebrew stores as UTF-8 bytes directly.

CLI:
    python tlou_loc.py decode <file>              # -> JSON {sid_hex: value}
    python tlou_loc.py dump   <file> [--n 40]     # human sample
    python tlou_loc.py stats  <file>
"""
import sys, os, json, struct, argparse


def decode(data):
    """Return (records, blob_start). records = list of (sid:int, offset:int, value:str)."""
    (count,) = struct.unpack_from("<I", data, 0)
    blob_start = 4 + count * 16
    recs = []
    off = 4
    for _ in range(count):
        sid, boff = struct.unpack_from("<QQ", data, off)
        off += 16
        p = blob_start + boff
        end = data.find(b"\x00", p)
        if end < 0:
            end = len(data)
        val = data[p:end].decode("utf-8", "replace")
        recs.append((sid, boff, val))
    return recs, blob_start


def to_map(data):
    """SID(hex) -> value, keeping order; last write wins (dupes are identical)."""
    recs, _ = decode(data)
    return {f"{sid:016x}": val for sid, _o, val in recs}


def encode(orig_data, overrides):
    """SURGICAL rebuild: keep the ORIGINAL blob byte-for-byte and every
    unchanged record's original offset; only the overridden SIDs get a new
    value APPENDED to the tail of the blob (deduped among themselves).

    ⚠️ Why surgical (learned in-game on TLOU2R 2026-07-07): a full rebuild
    (reorder + re-dedup the whole blob) is read back CORRECTLY by our own
    decoder — the offset table stays consistent — but the GAME ENGINE reads
    unchanged strings WRONG (e.g. "Downtown" -> "Tntoe"), because the engine
    relies on the original blob layout / offsets (sid-lookup references them).
    So `encode(orig, {})` MUST be byte-identical to `orig`, and an override
    must not move a single unchanged byte. Grows freely (offsets are u64).

    overrides: SID-hex -> new UTF-8 string. Returns new bytes."""
    recs, blob_start = decode(orig_data)
    (count,) = struct.unpack_from("<I", orig_data, 0)
    new_blob = bytearray(orig_data[blob_start:])   # ORIGINAL blob, untouched
    appended = {}                                  # new value bytes -> tail offset
    new_recs = []
    for sid, oldoff, _oldval in recs:
        key = f"{sid:016x}"
        if key in overrides:
            b = overrides[key].encode("utf-8")
            if b not in appended:
                appended[b] = len(new_blob)
                new_blob += b + b"\x00"
            new_recs.append((sid, appended[b]))
        else:
            new_recs.append((sid, oldoff))         # unchanged -> ORIGINAL offset
    out = bytearray()
    out += struct.pack("<I", count)
    for sid, boff in new_recs:
        out += struct.pack("<QQ", sid, boff)
    out += new_blob
    return bytes(out)


# --------------------------------------------------------------------------
def _load(path):
    with open(path, "rb") as f:
        return f.read()


def _cmd_decode(a):
    data = _load(a.file)
    m = to_map(data)
    out = a.out or (a.file + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    print(f"{len(m)} strings -> {out}")


def _cmd_dump(a):
    data = _load(a.file)
    recs, bs = decode(data)
    print(f"count={len(recs)}  blob_start={bs}  file={len(data)}")
    for sid, off, val in recs[:a.n]:
        v = val.replace("\n", "\\n")
        print(f"  {sid:016x}  @{off:<8} {v[:90]!r}")


def _cmd_stats(a):
    data = _load(a.file)
    recs, bs = decode(data)
    vals = [v for _s, _o, v in recs]
    nonempty = [v for v in vals if v.strip()]
    uniq = len(set(vals))
    import statistics
    lens = [len(v) for v in nonempty] or [0]
    print(f"records      : {len(recs)}")
    print(f"unique values: {uniq}")
    print(f"non-empty    : {len(nonempty)}")
    print(f"len median/max: {int(statistics.median(lens))}/{max(lens)}")
    # roundtrip check (no overrides)
    rebuilt = encode(data, {})
    rr, _ = decode(rebuilt)
    same = [v for _s, _o, v in rr] == vals
    print(f"roundtrip values identical: {same}  (rebuilt {len(rebuilt)} vs {len(data)} bytes)")


def main():
    ap = argparse.ArgumentParser(description="TLOU Part I loc codec")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode"); d.add_argument("file"); d.add_argument("--out")
    d = sub.add_parser("dump");   d.add_argument("file"); d.add_argument("--n", type=int, default=40)
    d = sub.add_parser("stats");  d.add_argument("file")
    a = ap.parse_args()
    {"decode": _cmd_decode, "dump": _cmd_dump, "stats": _cmd_stats}[a.cmd](a)


if __name__ == "__main__":
    main()
