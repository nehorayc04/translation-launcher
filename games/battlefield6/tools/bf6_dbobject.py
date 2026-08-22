"""
Battlefield 6 (Frostbite) DbObject reader — read-only, pure Python, no external deps.

DbObject is Frostbite's generic recursive key-value binary serialization format, used
across the engine for `layout.toc`, `chunkmanifest`, and many other manifest/config
files (NOT just BF6 — it's the same format going back to early Frostbite titles).

Format reverse-engineered by decompiling `FMT.FileTools.Readers.DbReader` (found inside
the FMT.exe .NET single-file bundle, carved out as its own assembly and decompiled with
ilspycmd — see bf6_toc.py's module docstring for the general methodology).

A DbObject-bearing file (e.g. `layout.toc`) starts with the SAME 556-byte header as a
regular `.toc` (see bf6_toc.py): 4-byte big-endian magic (0x00D1CE00 or 0x00D1CE01) +
4 zero bytes, then (only for the 0x...01 variant) a 260-byte XOR-obfuscated key at a
fixed offset of 296 (XOR constant 0x7B) — unused for BF6 (CreateDeobfuscator() always
returns a NullDeobfuscator here). Real DbObject content starts at the fixed offset 556,
exactly like a regular .toc's MetaData.

DbObject encoding, one recursive "field" at a time:
    byte tag
    DbType = tag & 0x1F          # low 5 bits = type
    if (tag & 0x80) == 0:        # bit 0x80 set  => this is an unnamed array element
        name = read_cstring()    # bit 0x80 clear => named dict field, read its name
    switch DbType:
        0                -> end-of-collection sentinel (used internally, not returned)
        1  (Array)        -> byteLen:7bit-varint, then read child fields until
                              bytes_consumed >= byteLen  -> Python list
        2  (Dict/Object)  -> byteLen:7bit-varint, then read {name: child} pairs until
                              bytes_consumed >= byteLen  -> Python dict (case-insens.)
        6  (Bool)         -> 1 byte (1=True)
        7  (String)       -> strLen:7bit-varint, then strLen raw bytes (utf-8)
        8  (Int32)        -> 4 bytes LE
        9  (Int64/Long)   -> 8 bytes LE
        11 (Float)        -> 4 bytes LE
        12 (Double)       -> 8 bytes LE
        15 (Guid)         -> 16 bytes raw
        16 (Sha1)         -> 20 bytes raw
        19 (ByteArray)    -> byteLen:7bit-varint, then byteLen raw bytes
        112 (0x70, top-level "Long" marker) -> 8 bytes LE (rare, not seen in layout.toc)
        anything else     -> unimplemented in FMT itself -> None

7-bit-encoded int/long = the standard .NET "Read7BitEncodedInt" varint: base-128,
least-significant-group first, continuation bit 0x80 per byte.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

MAGIC_NOKEY = 0x00D1CE00
MAGIC_KEY = 0x00D1CE01


def read_7bit_encoded(data: bytes, pos: int) -> tuple[int, int]:
    """Standard .NET 7-bit-encoded varint (unsigned). Returns (value, new_pos)."""
    result = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return result, pos


def read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.index(b"\x00", pos)
    return data[pos:end].decode("utf-8", errors="replace"), end + 1


def read_db_object(data: bytes, pos: int) -> tuple[object | None, str, int]:
    """Returns (value, name, new_pos). name is '' for unnamed/array elements."""
    tag = data[pos]
    pos += 1
    dbtype = tag & 0x1F
    if dbtype == 0:
        return None, "", pos
    name = ""
    if (tag & 0x80) == 0:
        name, pos = read_cstring(data, pos)

    if dbtype == 1:  # Array
        byte_len, pos = read_7bit_encoded(data, pos)
        start = pos
        items = []
        while pos - start < byte_len:
            val, _n, pos = read_db_object(data, pos)
            if val is None and pos - start >= byte_len:
                break
            items.append(val)
        return items, name, start + byte_len

    if dbtype == 2:  # Dict/Object
        byte_len, pos = read_7bit_encoded(data, pos)
        start = pos
        obj: dict[str, object] = {}
        while pos - start < byte_len:
            val, child_name, pos = read_db_object(data, pos)
            if val is None and pos - start >= byte_len:
                break
            obj[child_name] = val
        return obj, name, start + byte_len

    if dbtype == 6:  # Bool
        val = data[pos] == 1
        return val, name, pos + 1

    if dbtype == 7:  # String
        str_len, pos = read_7bit_encoded(data, pos)
        val = data[pos:pos + str_len].decode("utf-8", errors="replace")
        return val, name, pos + str_len

    if dbtype == 8:  # Int32
        val = struct.unpack_from("<i", data, pos)[0]
        return val, name, pos + 4

    if dbtype == 9:  # Int64
        val = struct.unpack_from("<q", data, pos)[0]
        return val, name, pos + 8

    if dbtype == 11:  # Float
        val = struct.unpack_from("<f", data, pos)[0]
        return val, name, pos + 4

    if dbtype == 12:  # Double
        val = struct.unpack_from("<d", data, pos)[0]
        return val, name, pos + 8

    if dbtype == 15:  # Guid
        val = data[pos:pos + 16]
        return val, name, pos + 16

    if dbtype == 16:  # Sha1
        val = data[pos:pos + 20]
        return val, name, pos + 20

    if dbtype == 19:  # ByteArray
        byte_len, pos = read_7bit_encoded(data, pos)
        val = data[pos:pos + byte_len]
        return val, name, pos + byte_len

    if dbtype == 0x10 and tag == 0x70:  # top-level Long marker (rare)
        val = struct.unpack_from("<q", data, pos)[0]
        return val, name, pos + 8

    # unimplemented type in FMT itself (2,3,4,9-dup,12-dup,13,16-dup,17) -> None
    return None, name, pos


def read_dbobject_file(path: str | Path) -> object:
    """Reads a whole DbObject-bearing file (e.g. layout.toc): validates the standard
    556-byte TOC-family header, then parses ONE top-level DbObject at offset 556."""
    path = Path(path)
    data = path.read_bytes()
    magic = struct.unpack_from(">I", data, 0)[0]
    if magic not in (MAGIC_NOKEY, MAGIC_KEY):
        raise ValueError(f"{path}: unexpected magic 0x{magic:08x}")
    off = 556
    val, _name, _pos = read_db_object(data, off)
    return val


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: bf6_dbobject.py <file> [dotted.path.to.print]")
        return 1
    obj = read_dbobject_file(argv[0])
    target = obj
    if len(argv) > 1:
        for part in argv[1].split("."):
            if isinstance(target, list):
                target = target[int(part)]
            elif isinstance(target, dict):
                target = target.get(part)
            else:
                target = None
                break

    def summarize(v, depth=0, max_depth=3):
        indent = "  " * depth
        if isinstance(v, dict):
            print(f"{indent}{{dict, {len(v)} keys}}: {list(v.keys())[:20]}")
            if depth < max_depth:
                for k, vv in list(v.items())[:10]:
                    print(f"{indent}  {k}:", end=" ")
                    summarize(vv, depth + 1, max_depth)
        elif isinstance(v, list):
            print(f"{indent}[list, {len(v)} items]")
            if depth < max_depth:
                for item in v[:5]:
                    summarize(item, depth + 1, max_depth)
        elif isinstance(v, (bytes, bytearray)):
            print(f"{indent}<bytes len={len(v)}> {v[:20].hex()}")
        else:
            print(f"{indent}{v!r}")

    summarize(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
