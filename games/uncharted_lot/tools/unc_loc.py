#!/usr/bin/env python3
r"""
unc_loc.py — codec for UNCHARTED: Legacy of Thieves Collection "text2" strings
(`<lang>.common`, `<lang>.subtitles`, `eng.subtitles-systemic`), the Naughty Dog
string table. Pure-Python, self-testing round-trip.

Same family as The Last of Us Part I/II (`games/tlou1/tools/tlou_loc.py`) but the
RECORD WIDTH IS NOT FIXED — it differs per file type, which is why the TLOU codec
returns empty strings on `.common` / `.subtitles`:

    uint32 count
    count * record            # record = {sid, blobOffset}, both LE
    blob:  UTF-8, NUL-terminated strings at (blob_start + blobOffset)
           blob_start = 4 + count * REC

    REC = 8   ->  <II>   (u32 sid, u32 offset)   .common / .subtitles
    REC = 16  ->  <QQ>   (u64 sid, u64 offset)   .subtitles-systemic  (+ sid-lookup)

`detect_rec()` picks the width by validating that blob_start lands exactly where
the string blob begins and that every offset is in range — never guess it.

* sid is the SAME across every language file  ->  map EN->HE by sid.
* Multiple records may share one blobOffset (deduped identical strings).
* UTF-8, so Hebrew stores directly.

CLI:
    python unc_loc.py detect <file>
    python unc_loc.py decode <file> [--out x.json]
    python unc_loc.py dump   <file> [--n 40]
    python unc_loc.py stats  <file>
    python unc_loc.py selftest <file> [file ...]
"""
import sys
import os
import json
import struct
import argparse

_FMT = {8: "<II", 16: "<QQ"}


def _try(data, rec):
    """Return (ok, blob_start). Validate a candidate record width."""
    if len(data) < 4:
        return False, 0
    (count,) = struct.unpack_from("<I", data, 0)
    blob_start = 4 + count * rec
    if count == 0 or blob_start > len(data):
        return False, blob_start
    blob_len = len(data) - blob_start
    fmt = _FMT[rec]
    # every offset must land inside the blob; sample generously but cheaply
    step = max(1, count // 512)
    for i in range(0, count, step):
        _sid, off = struct.unpack_from(fmt, data, 4 + i * rec)
        if off >= blob_len:
            return False, blob_start
    # the blob must actually start with a NUL-terminated string, and the record
    # table must not end mid-string (blob_start-1 is the last table byte)
    end = data.find(b"\x00", blob_start)
    if end < 0 or end == blob_start:      # empty first string = wrong split
        return False, blob_start
    try:
        data[blob_start:end].decode("utf-8")
    except UnicodeDecodeError:
        return False, blob_start
    return True, blob_start


def detect_rec(data):
    """8 or 16 — the record width this file really uses."""
    cands = [rec for rec in (8, 16) if _try(data, rec)[0]]
    if not cands:
        raise ValueError("unrecognised ND loc file (neither 8- nor 16-byte records fit)")
    if len(cands) == 1:
        return cands[0]
    # both "fit" -> prefer the one whose blob_start is the tighter fit, i.e. the
    # larger table (a too-small table leaves record bytes at the head of the blob)
    return max(cands)


def decode(data, rec=None):
    """Return (records, blob_start, rec). records = list of (sid, offset, value)."""
    if rec is None:
        rec = detect_rec(data)
    (count,) = struct.unpack_from("<I", data, 0)
    blob_start = 4 + count * rec
    fmt = _FMT[rec]
    recs = []
    off = 4
    for _ in range(count):
        sid, boff = struct.unpack_from(fmt, data, off)
        off += rec
        p = blob_start + boff
        end = data.find(b"\x00", p)
        if end < 0:
            end = len(data)
        recs.append((sid, boff, data[p:end].decode("utf-8", "replace")))
    return recs, blob_start, rec


def to_map(data, rec=None):
    """sid(hex) -> value. Width-aware key (8 or 16 hex digits)."""
    recs, _bs, rec = decode(data, rec)
    w = rec * 2 // 2  # 8 hex digits for u32, 16 for u64
    w = 8 if rec == 8 else 16
    return {f"{sid:0{w}x}": val for sid, _o, val in recs}


def encode(orig_data, overrides):
    """SURGICAL rebuild: keep the ORIGINAL blob byte-for-byte and every unchanged
    record's original offset; only overridden sids get a value APPENDED to the
    blob tail (deduped among themselves).

    ⚠️ Surgical, never a full rebuild — the engine relies on the original blob
    layout (a rebuilt/reordered blob reads back fine in Python but renders as
    scrambled text in-game; proven on TLOU2R 2026-07-07, same ND codec).

    `overrides` maps sid(hex str, any case) or sid(int) -> new value.
    """
    recs, blob_start, rec = decode(orig_data)
    w = 8 if rec == 8 else 16
    ov = {}
    for k, v in overrides.items():
        ov[int(k, 16) if isinstance(k, str) else int(k)] = v

    blob = bytearray(orig_data[blob_start:])
    tail_cache = {}
    new_recs = []
    for sid, boff, _val in recs:
        if sid in ov:
            s = ov[sid]
            if s in tail_cache:
                boff = tail_cache[s]
            else:
                boff = len(blob)
                blob += s.encode("utf-8") + b"\x00"
                tail_cache[s] = boff
        new_recs.append((sid, boff))

    fmt = _FMT[rec]
    out = bytearray(struct.pack("<I", len(new_recs)))
    for sid, boff in new_recs:
        out += struct.pack(fmt, sid, boff)
    out += blob
    return bytes(out)


# --------------------------------------------------------------------------- CLI
def _load(path):
    with open(path, "rb") as fh:
        return fh.read()


def _cmd_detect(a):
    d = _load(a.file)
    rec = detect_rec(d)
    (count,) = struct.unpack_from("<I", d, 0)
    print(f"{os.path.basename(a.file)}: rec={rec}B count={count:,} blob_start={4+count*rec:,} size={len(d):,}")


def _cmd_decode(a):
    d = _load(a.file)
    m = to_map(d)
    out = a.out or (a.file + ".json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=0)
    print(f"{len(m):,} sids -> {out}")


def _cmd_dump(a):
    recs, bs, rec = decode(_load(a.file))
    w = 8 if rec == 8 else 16
    for sid, off, val in recs[: a.n]:
        print(f"{sid:0{w}x}  @{off:<9} {val!r}")
    print(f"\n[{len(recs):,} records, rec={rec}B, blob_start={bs:,}]", file=sys.stderr)


def _cmd_stats(a):
    recs, bs, rec = decode(_load(a.file))
    vals = [v for _s, _o, v in recs]
    nonempty = [v for v in vals if v]
    print(f"file        : {a.file}")
    print(f"rec width   : {rec} bytes")
    print(f"records     : {len(recs):,}")
    print(f"unique sid  : {len({s for s,_,_ in recs}):,}")
    print(f"unique value: {len(set(vals)):,}")
    print(f"non-empty   : {len(nonempty):,}")
    print(f"chars       : {sum(len(v) for v in set(vals)):,}")


def _cmd_selftest(a):
    ok = True
    for f in a.files:
        d = _load(f)
        rec = detect_rec(d)
        ident = encode(d, {})
        same = ident == d
        recs, _bs, _r = decode(d)
        # override round-trip
        probe = {f"{recs[0][0]:x}": "בדיקה עברית"}
        mod = encode(d, probe)
        back = to_map(mod)
        k = list(to_map(d).keys())[0]
        rt = back[k] == "בדיקה עברית"
        # all other values preserved?
        orig_map = to_map(d)
        others = all(back[kk] == vv for kk, vv in orig_map.items() if kk != k)
        good = same and rt and others
        ok &= good
        print(f"[{'PASS' if good else 'FAIL'}] {os.path.basename(f):26s} rec={rec:2d} "
              f"identity={'byte-identical' if same else 'DIFFERS'} override={rt} others_intact={others}")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT loc codec")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("detect"); s.add_argument("file")
    s = sub.add_parser("decode"); s.add_argument("file"); s.add_argument("--out")
    s = sub.add_parser("dump");   s.add_argument("file"); s.add_argument("--n", type=int, default=40)
    s = sub.add_parser("stats");  s.add_argument("file")
    s = sub.add_parser("selftest"); s.add_argument("files", nargs="+")
    a = ap.parse_args()
    {"detect": _cmd_detect, "decode": _cmd_decode, "dump": _cmd_dump,
     "stats": _cmd_stats, "selftest": _cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
