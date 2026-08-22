"""Extract the #US (user string) heap from a .NET assembly.

Every string literal a C# method can push with `ldstr` lives in this heap, so
it is the exact, complete inventory of code-side text -- far better than a
regex over the file (no false positives from metadata names or blobs) and it
gives each literal's byte offset, which is what a surgical patcher needs.

PE -> COR20 header -> metadata root -> stream headers -> #US.
Entries: [compressed-uint32 byteLen][UTF-16LE chars][1 trailing flag byte]
byteLen counts the chars + the flag byte; a length of 0 is the empty slot.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UserString:
    offset: int  # absolute file offset of the char data
    char_len: int  # number of UTF-16 code units
    text: str


def _rva_to_off(data: bytes, rva: int, sections) -> int:
    for va, vsize, raw_ptr, raw_size in sections:
        if va <= rva < va + max(vsize, raw_size):
            return raw_ptr + (rva - va)
    raise ValueError(f"RVA 0x{rva:x} not in any section")


def _read_compressed_uint(data: bytes, pos: int) -> tuple[int, int]:
    b0 = data[pos]
    if b0 & 0x80 == 0:
        return b0, pos + 1
    if b0 & 0x40 == 0:
        return ((b0 & 0x3F) << 8) | data[pos + 1], pos + 2
    v = ((b0 & 0x1F) << 24) | (data[pos + 1] << 16) | (data[pos + 2] << 8) | data[pos + 3]
    return v, pos + 4


def _sections(data: bytes):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe : pe + 4] == b"PE\0\0", "not a PE"
    n_sec = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    magic = struct.unpack_from("<H", data, pe + 24)[0]
    sec_off = pe + 24 + opt_size
    secs = []
    for i in range(n_sec):
        o = sec_off + i * 40
        vsize, va, raw_size, raw_ptr = struct.unpack_from("<IIII", data, o + 8)
        secs.append((va, vsize, raw_ptr, raw_size))
    # CLI header is data directory #14
    dd = pe + 24 + (112 if magic == 0x20B else 96)
    cli_rva, cli_size = struct.unpack_from("<II", data, dd + 14 * 8)
    return secs, cli_rva


def read_us_heap(path) -> list[UserString]:
    data = Path(path).read_bytes()
    secs, cli_rva = _sections(data)
    if not cli_rva:
        return []
    cli = _rva_to_off(data, cli_rva, secs)
    md_rva, md_size = struct.unpack_from("<II", data, cli + 8)
    md = _rva_to_off(data, md_rva, secs)
    assert data[md : md + 4] == b"BSJB", "bad metadata signature"

    ver_len = struct.unpack_from("<I", data, md + 12)[0]
    pos = md + 16 + ver_len
    pos += 2  # flags
    n_streams = struct.unpack_from("<H", data, pos)[0]
    pos += 2

    us_off = us_size = 0
    for _ in range(n_streams):
        off, size = struct.unpack_from("<II", data, pos)
        pos += 8
        end = data.index(b"\0", pos)
        name = data[pos:end].decode("ascii")
        pos = end + 1
        pos = (pos + 3) & ~3  # 4-byte aligned
        if name == "#US":
            us_off, us_size = off, size
    if not us_size:
        return []

    base = md + us_off
    out: list[UserString] = []
    p = base + 1  # heap[0] is always a single 0x00
    end = base + us_size
    while p < end:
        blob_len, q = _read_compressed_uint(data, p)
        if blob_len == 0:
            p = q
            continue
        n_chars = (blob_len - 1) // 2
        try:
            txt = data[q : q + n_chars * 2].decode("utf-16le")
        except UnicodeDecodeError:
            txt = data[q : q + n_chars * 2].decode("utf-16le", "replace")
        out.append(UserString(q, n_chars, txt))
        p = q + blob_len
    return out


if __name__ == "__main__":
    import sys

    p = sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Winhanced\Winhanced.dll"
    us = read_us_heap(p)
    print(f"{Path(p).name}: {len(us)} user strings")
    sent = [u for u in us if " " in u.text.strip() and len(u.text.strip()) > 3]
    print(f"  with a space (sentence-like): {len(sent)}")
    for u in sent[:40]:
        print(f"   @0x{u.offset:07x} {u.text[:88]!r}")
