"""Bethesda string-table codec — .STRINGS / .DLSTRINGS / .ILSTRINGS (Skyrim SE / AE).

Layout (all little-endian):
    u32 count
    u32 dataSize                     # bytes of the data section
    count x { u32 stringID, u32 offset }   # offset is RELATIVE to the data section
    data section (starts at 8 + count*8):
        .STRINGS              -> NUL-terminated bytes
        .DLSTRINGS/.ILSTRINGS -> u32 length (INCLUDING the trailing NUL) + bytes

Encoding: Skyrim SPECIAL EDITION stores **UTF-8** for every language
(verified empirically: ru/ja/pl values are UTF-8 multi-byte, not cp1251/932/1250).
Original Skyrim LE used per-language ANSI codepages -- do NOT reuse LE tooling.

Duplicate offsets are legal and common: identical values share one data blob.
`encode()` preserves that by de-duplicating on the byte value, which is what the
shipped files already do.

CLI:  python strings.py info   <file>
      python strings.py dump   <file> [out.json]
      python strings.py rt     <file>          # identity round-trip check
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

LONG_EXT = {".dlstrings", ".ilstrings"}


def is_long(path: str | Path) -> bool:
    return Path(path).suffix.lower() in LONG_EXT


def decode(data: bytes, long_form: bool) -> dict[int, str]:
    count, _dsize = struct.unpack_from("<II", data, 0)
    base = 8 + count * 8
    out: dict[int, str] = {}
    for i in range(count):
        sid, off = struct.unpack_from("<II", data, 8 + i * 8)
        p = base + off
        if long_form:
            ln = struct.unpack_from("<I", data, p)[0]
            raw = data[p + 4: p + 4 + ln]
            if raw.endswith(b"\x00"):
                raw = raw[:-1]
        else:
            e = data.index(b"\x00", p)
            raw = data[p:e]
        out[sid] = raw.decode("utf-8", errors="replace")
    return out


def encode(entries: dict[int, str], long_form: bool) -> bytes:
    """Rebuild a table. IDs are emitted in ascending order (as shipped)."""
    ids = sorted(entries)
    blobs: list[bytes] = []
    seen: dict[bytes, int] = {}
    offsets: dict[int, int] = {}
    cur = 0
    for sid in ids:
        raw = entries[sid].encode("utf-8")
        if raw in seen:
            offsets[sid] = seen[raw]
            continue
        seen[raw] = cur
        offsets[sid] = cur
        if long_form:
            rec = struct.pack("<I", len(raw) + 1) + raw + b"\x00"
        else:
            rec = raw + b"\x00"
        blobs.append(rec)
        cur += len(rec)
    body = b"".join(blobs)
    head = struct.pack("<II", len(ids), len(body))
    dirt = b"".join(struct.pack("<II", sid, offsets[sid]) for sid in ids)
    return head + dirt + body


def load(path: str | Path) -> dict[int, str]:
    p = Path(path)
    return decode(p.read_bytes(), is_long(p))


def save(path: str | Path, entries: dict[int, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(encode(entries, is_long(p)))


def roundtrip(path: str | Path) -> tuple[bool, bool, str]:
    """(semantic_ok, byte_identical, note)"""
    p = Path(path)
    orig = p.read_bytes()
    ent = decode(orig, is_long(p))
    rebuilt = encode(ent, is_long(p))
    again = decode(rebuilt, is_long(p))
    semantic = ent == again
    return semantic, rebuilt == orig, f"{len(ent)} entries, {len(orig)} -> {len(rebuilt)} B"


def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    if cmd == "info":
        e = load(path)
        n = sum(len(v) for v in e.values())
        print(f"{path}: {len(e)} entries, {n} chars, long={is_long(path)}")
        for sid in sorted(e)[:5]:
            print(f"  {sid:<10} {e[sid][:90]!r}")
        return 0
    if cmd == "dump":
        e = load(path)
        out = argv[3] if len(argv) > 3 else path + ".json"
        Path(out).write_text(json.dumps({str(k): v for k, v in sorted(e.items())},
                                        ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{len(e)} -> {out}")
        return 0
    if cmd == "rt":
        sem, ident, note = roundtrip(path)
        print(f"{'PASS' if sem else 'FAIL'} semantic | "
              f"{'byte-identical' if ident else 'byte-DIFFERENT'} | {note}")
        return 0 if sem else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
