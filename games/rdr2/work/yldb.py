#!/usr/bin/env python3
"""Reader for RDR2's `.yldb` language database (the game's OWN text, per language).

Cracked 2026-08-07 from the unpacked archives. A `.yldb` is a RAGE resource whose payload
is a flat array of 64-byte nodes; the strings sit inline in the same buffer:

    +0x00  u64 strPtr    RSC virtual pointer -- file offset = ptr & 0x0FFFFFFF
    +0x08  u64 strLen    byte length INCLUDING the terminating NUL
    +0x10  u32 hash      the JOAAT text key -- exactly the `0xHASH` the LML mod uses
    +0x14  u32 0
    +0x18  u64 / +0x20 u64   tree links (unused here)
    +0x28..0x3F  zero

Verified on real files: ptr 0x500000E0 / len 0x3B resolves to the 58-char string
"~z~~sl:4.7:0.9~Here...~sl:1.5~some money for your trouble." plus its NUL.

Nodes are found by SCANNING on a 16-byte grid and validating every field against the file,
rather than trusting a header -- the extractor strips each resource's 16-byte header, so
absolute header offsets are unreliable while the self-consistency check is not.
"""
from __future__ import annotations

import os
import struct
import sys

PTR_MASK = 0x0FFFFFFF
PTR_TAGS = (0x50, 0x60)          # RSC virtual / physical page bases


def parse(data: bytes) -> dict[int, str]:
    """Return {hash: text} for one .yldb buffer."""
    out: dict[int, str] = {}
    n = len(data)
    for off in range(0, n - 24, 16):
        ptr, ln = struct.unpack_from("<QQ", data, off)
        if ln < 1 or ln > 65536:
            continue
        if (ptr >> 32) != 0 or ((ptr >> 24) & 0xFF) not in PTR_TAGS:
            continue
        s = ptr & PTR_MASK
        if s + ln > n or s == 0:
            continue
        h = struct.unpack_from("<I", data, off + 16)[0]
        if h == 0:
            continue
        raw = data[s:s + ln]
        if raw[-1:] != b"\x00":            # the length must cover the NUL exactly
            continue
        body = raw[:-1]
        if b"\x00" in body:                # a real string has no embedded NUL
            continue
        try:
            txt = body.decode("utf-8")
        except UnicodeDecodeError:
            continue
        out[h] = txt
    return out


def parse_file(path: str) -> dict[int, str]:
    with open(path, "rb") as fh:
        return parse(fh.read())


def parse_dir(folder: str) -> dict[int, str]:
    """Merge every .yldb in a language folder. Later files win (patch order)."""
    out: dict[int, str] = {}
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".yldb"):
            continue
        try:
            out.update(parse_file(os.path.join(folder, name)))
        except OSError:
            pass
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    tgt = sys.argv[1]
    m = parse_dir(tgt) if os.path.isdir(tgt) else parse_file(tgt)
    print(f"{len(m):,} string(s)")
    for i, (h, t) in enumerate(m.items()):
        if i >= 15:
            break
        print(f"  0x{h:08X}  {t[:90]!r}")
