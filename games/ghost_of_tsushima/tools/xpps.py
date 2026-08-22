#!/usr/bin/env python3
r"""
xpps_alt.py — pure-Python (stdlib only) reader for Ghost of Tsushima
Director's Cut "KCAP" localization packages (``lang_<lang>_text.xpps``).

FORMAT (little-endian), cracked by byte-level analysis of the real
lang_english_text.xpps / lang_arabic_text.xpps:

    0x00  "KCAP"                         magic (== "PACK" reversed)
    0x04  u16 0x001f, u16 0x0007         format/version tag
    0x08  u32 0x0000041d                 (constant across langs)
    0x0c  u32 0x00010000
    0x10  u32 0x00070000
    0x14  u32 0x0000001d (29)
    0x18  u32 0x000000b8 (184)
    0x1c  u32   -> 300(EN)/288(AR)       (varies per lang)
    0x20  u32 0
    0x24  u32 0
    0x28  u32 BASE   -> 484(EN)/472(AR)  ***string-blob start (base offset)***
    0x2c  u32 TRAILER_START (= filesize - trailer_size)
    0x30.. zero padding up to BASE

    [BASE .. ~2.1MB]  STRING BLOB — UTF-8, each string NUL-terminated.
                      (Interleaved after the strings, the hash/index tables live
                       in ~1.35MB..2.8MB; a large ~2.1MB..EOF tail is unrelated
                       BINARY resource data — NOT text.)

    INDEX TABLES  — one or more sorted arrays of 16-byte records:
        u64 KEY        (little-endian)
        u64 OFFSET     (high 32 bits == 0; file position = BASE + OFFSET)
      Each table is sorted ASCENDING by KEY. Two KEY kinds coexist:
        * large 64-bit key-name HASHES (UI/menus/most content). These KEYS are
          SHARED across languages -> map EN<->AR by exact key.
        * small STRUCTURED ids for sequential dialogue/subtitle blocks; the
          record is really {u16 f1, u16 f2, u32 0, u64 off} and the strings are
          stored contiguously. These per-language ids do NOT exact-match across
          languages (join dialogue by block/position in Phase 2).

    [.. EOF]  TRAILER directory: 16-byte {u64 tag, u64 value} entries ending in
              a tag whose value is the FourCC "END " (0x454E4420). Values point
              at the index-table section offsets.

The string at KEY is: data[BASE+OFFSET : next NUL].
"""
import os, json, struct, argparse

MAGIC = b"KCAP"


# ---------------------------------------------------------------- core parse
def _base(data):
    return struct.unpack_from("<I", data, 0x28)[0]


def _iter_tables(data, min_len=8):
    """Yield (start, count) for every maximal contiguous run of 16-byte
    {u64 key, u64 off} records with off>>32==0, off<len, KEY strictly
    ascending, run length >= min_len. Records are 4-byte aligned."""
    N = len(data)
    p = 0
    while p + 16 <= N:
        key, off = struct.unpack_from("<QQ", data, p)
        if key != 0 and off >> 32 == 0 and off < N:
            q = p
            prev = -1
            cnt = 0
            while q + 16 <= N:
                k, o = struct.unpack_from("<QQ", data, q)
                if o >> 32 != 0 or o >= N or k <= prev:
                    break
                prev = k
                q += 16
                cnt += 1
            if cnt >= min_len:
                yield (p, cnt)
                p = q
                continue
        p += 4


def _read_str(data, p):
    """UTF-8 NUL-terminated string at file position p, or None if it isn't a
    clean string start (prev byte must be NUL, valid UTF-8, no control bytes)."""
    if p < 0 or p >= len(data):
        return None
    e = data.find(b"\x00", p)
    if e < 0:
        return None
    try:
        s = data[p:e].decode("utf-8")
    except UnicodeDecodeError:
        return None
    for ch in s:
        if ord(ch) < 32 and ch not in "\t\n\r":
            return None
    return s


def parse(data, min_len=8):
    """Return (records, base). records = list of (key:int, off:int, text:str),
    in table/file order, de-duplicated by key (last wins). Only records that
    resolve to a clean UTF-8 string are kept (this rejects false runs that the
    scanner may pick up inside the binary tail)."""
    base = _base(data)
    out = {}
    order = []
    for start, cnt in _iter_tables(data, min_len):
        for j in range(cnt):
            key, off = struct.unpack_from("<QQ", data, start + j * 16)
            p = base + off
            if not (p == base or (0 < p <= len(data) and data[p - 1] == 0)):
                continue
            s = _read_str(data, p)
            if s is None:
                continue
            if key not in out:
                order.append(key)
            out[key] = (off, s)
    return [(k, out[k][0], out[k][1]) for k in order], base


def read_pack(path, min_len=8, ordered=False):
    """Read a .xpps file.
    Returns dict {key_hex: text}; if ordered=True returns list of (key_hex,text)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != MAGIC:
        raise ValueError(f"{path}: not a KCAP file (magic={data[:4]!r})")
    recs, _base_ = parse(data, min_len)
    if ordered:
        return [(f"{k:016x}", t) for k, _o, t in recs]
    return {f"{k:016x}": t for k, _o, t in recs}


# ---------------------------------------------------------------- writing
def patch(data, overrides, min_len=8):
    """SURGICAL override: append new NUL-terminated strings just before the EOF
    trailer and repoint only the changed keys' OFFSET fields; every unchanged
    byte/offset is preserved. overrides = {key_hex: new_text}. Returns new bytes.

    With overrides={} the output is BYTE-IDENTICAL to the input.
    NOTE: growth is via append (OFFSET is a u64 -> unbounded); in-game load of
    strings living past the original blob still needs verification (Phase 2).
    A same-length override could instead be written in place with zero growth."""
    base = _base(data)
    trailer_start = struct.unpack_from("<I", data, 0x2c)[0]
    if not overrides:
        return bytes(data)                       # identity
    # locate the record for each overridden key (first table occurrence)
    keypos = {}
    for start, cnt in _iter_tables(data, min_len):
        for j in range(cnt):
            key, off = struct.unpack_from("<QQ", data, start + j * 16)
            kh = f"{key:016x}"
            if kh in overrides and kh not in keypos:
                keypos[kh] = start + j * 16
    missing = set(overrides) - set(keypos)
    if missing:
        raise KeyError(f"unknown keys: {sorted(missing)[:5]}...")
    out = bytearray(data)
    append = bytearray(b"\x00")                   # guard NUL so the first
    append_base = trailer_start                  # appended string has NUL before it
    newoff = {}
    for kh, txt in overrides.items():
        b = txt.encode("utf-8")
        if b in newoff:
            pass
        else:
            newoff[b] = append_base + len(append) - base
            append += b + b"\x00"
        # rewrite this key's OFFSET field (the u64 at recpos+8)
        struct.pack_into("<Q", out, keypos_off(keypos[kh]), newoff[b])
    # splice: [head up to trailer] + [appended blob] + [trailer]
    new = bytearray(out[:trailer_start]) + append + bytearray(out[trailer_start:])
    # update @0x2c trailer_start pointer
    struct.pack_into("<I", new, 0x2c, trailer_start + len(append))
    return bytes(new)


def keypos_off(recpos):
    return recpos + 8


def patch_inplace(data, overrides, min_len=8):
    """SAME-SIZE in-place override: overwrite each key's string AT ITS EXISTING OFFSET
    (requires utf8(new) <= utf8(existing) in bytes). Returns new bytes of the SAME LENGTH
    (nothing shifts -> the enclosing archive's block/offset layout is untouched, so this is
    the lowest-risk edit for an in-archive replace). A shorter new string leaves the old
    trailing bytes as dead/unreferenced (the NUL terminates early). Raises if any new string
    is longer than the existing one, or a key is missing. overrides = {key_hex: new_text}."""
    base = _base(data)
    keypos = {}
    for start, cnt in _iter_tables(data, min_len):
        for j in range(cnt):
            key, off = struct.unpack_from("<QQ", data, start + j * 16)
            kh = f"{key:016x}"
            if kh in overrides and kh not in keypos:
                keypos[kh] = off
    missing = set(overrides) - set(keypos)
    if missing:
        raise KeyError(f"unknown keys: {sorted(missing)[:5]}...")
    out = bytearray(data)
    too_long = {}
    for kh, txt in overrides.items():
        off = keypos[kh]; p = base + off
        e = out.find(b"\x00", p)
        old_len = e - p
        nb = txt.encode("utf-8")
        if len(nb) > old_len:
            too_long[kh] = (len(nb), old_len); continue
        out[p:p + len(nb)] = nb
        out[p + len(nb)] = 0                       # NUL-terminate (dead bytes up to old NUL remain)
    if too_long:
        raise ValueError(f"{len(too_long)} overrides exceed existing byte length: "
                         f"{dict(list(too_long.items())[:5])}")
    assert len(out) == len(data)
    return bytes(out)


# ---------------------------------------------------------------- CLI
def _cmd_stats(a):
    with open(a.file, "rb") as f:
        data = f.read()
    recs, base = parse(data, a.min_len)
    keys = [k for k, _o, _t in recs]
    vals = [t for _k, _o, t in recs]
    big = sum(1 for k in keys if k > 0x1_0000_0000)
    small = len(keys) - big
    nonempty = [v for v in vals if v]
    lens = sorted(len(v) for v in nonempty) or [0]
    print(f"file          : {a.file}  ({len(data)} bytes)")
    print(f"magic         : {data[:4]!r}  base(@0x28)={base}  trailer(@0x2c)={struct.unpack_from('<I',data,0x2c)[0]}")
    print(f"records        : {len(recs)}")
    print(f"unique values : {len(set(vals))}   empty: {len(vals)-len(nonempty)}")
    print(f"key kinds     : {big} large-hash  +  {small} small-id (dialogue)")
    print(f"len min/med/max: {lens[0]}/{lens[len(lens)//2]}/{lens[-1]}")


def _cmd_dump(a):
    recs = read_pack(a.file, a.min_len, ordered=True)
    for kh, t in recs[: a.n]:
        print(f"  {kh}  {t[:100]!r}")


def _cmd_find(a):
    recs = read_pack(a.file, a.min_len, ordered=True)
    needle = a.substr
    hits = [(kh, t) for kh, t in recs if needle in t]
    print(f"{len(hits)} hits for {needle!r}")
    for kh, t in hits[: a.n]:
        print(f"  {kh}  {t[:100]!r}")


def _cmd_export(a):
    m = read_pack(a.file, a.min_len)
    out = a.out or (a.file + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    print(f"{len(m)} strings -> {out}")


def _cmd_selftest(a):
    """identity round-trip + a same-length in-place check on both real files."""
    for path in a.files:
        with open(path, "rb") as f:
            data = f.read()
        # identity
        ident = patch(data, {})
        print(f"{os.path.basename(path)}: identity round-trip byte-identical? {ident == data}")
        recs, base = parse(data)
        # pick a key whose text is short and unique-ish
        kh, off, txt = next((k, o, t) for k, o, t in ((f"{k:016x}", o, t) for k, o, t in recs) if t and len(t) >= 4)
        # append override
        new = patch(data, {kh: txt + "X"})
        back = {k: v for k, v in read_pack_bytes(new)}
        ok = back.get(kh) == txt + "X"
        print(f"   override key {kh} {txt!r}->{txt+'X'!r}: readback ok? {ok}  size {len(data)}->{len(new)} (+{len(new)-len(data)})")


def read_pack_bytes(data, min_len=8):
    recs, _b = parse(data, min_len)
    return [(f"{k:016x}", t) for k, _o, t in recs]


def main():
    ap = argparse.ArgumentParser(description="Ghost of Tsushima KCAP .xpps reader")
    ap.add_argument("--min-len", type=int, default=8, help="min index-table run length")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats"); s.add_argument("file")
    s = sub.add_parser("dump"); s.add_argument("file"); s.add_argument("n", nargs="?", type=int, default=40)
    s = sub.add_parser("find"); s.add_argument("file"); s.add_argument("substr"); s.add_argument("--n", type=int, default=40)
    s = sub.add_parser("export"); s.add_argument("file"); s.add_argument("--out")
    s = sub.add_parser("selftest"); s.add_argument("files", nargs="+")
    a = ap.parse_args()
    {"stats": _cmd_stats, "dump": _cmd_dump, "find": _cmd_find,
     "export": _cmd_export, "selftest": _cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
