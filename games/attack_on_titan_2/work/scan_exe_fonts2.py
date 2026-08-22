"""Strict-validated sfnt scan of the AoT2 executables + PE resource check.
The prior pass's fontTools(lazy=True) loader accepted machine-code garbage as
"valid tables" (any 4-byte tag counts, no ASCII/offset sanity check) -- this
version enforces the REAL sfnt table-directory invariants by hand:
  - numTables in a sane range (1..64)
  - searchRange/entrySelector/rangeShift consistent with numTables (the sfnt
    spec defines these exactly from numTables -- a real font always agrees)
  - every table tag is 4 PRINTABLE ascii chars
  - every table's (offset, length) fits inside the buffer
"""
import struct
from pathlib import Path

import pefile

GAME = Path("F:/Games/Attack on Titan 2")
TARGETS = ["AOT2_EU.exe", "AOT2_AS.exe", "AOT2_JP.exe", "Launcher.exe"]
SFNT_MAGICS = [b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"]
RT_FONT = 8
RT_FONTDIR = 7


def _printable_tag(tag: bytes) -> bool:
    return all(0x20 <= b < 0x7F for b in tag)


def validate_sfnt(data: bytes, off: int, filesize: int):
    if off + 12 > filesize:
        return None
    num_tables, search_range, entry_selector, range_shift = struct.unpack_from(
        "<HHHH", data, off + 4
    )
    if not (1 <= num_tables <= 64):
        return None
    # sfnt spec: searchRange = (2^floor(log2(numTables))) * 16
    import math
    p2 = 1 << int(math.floor(math.log2(num_tables)))
    exp_search_range = p2 * 16
    exp_entry_selector = int(math.floor(math.log2(num_tables)))
    exp_range_shift = num_tables * 16 - exp_search_range
    if search_range != exp_search_range:
        return None
    if entry_selector != exp_entry_selector:
        return None
    if range_shift != exp_range_shift:
        return None
    dir_off = off + 12
    if dir_off + num_tables * 16 > filesize:
        return None
    tags = []
    for i in range(num_tables):
        tag, checksum, toff, tlen = struct.unpack_from("<4sIII", data, dir_off + i * 16)
        if not _printable_tag(tag):
            return None
        if toff + tlen > filesize or toff < off:
            return None
        tags.append(tag.decode("ascii"))
    return tags


def scan_pe_resources(path: Path):
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
        )
    except Exception as e:
        print(f"  [pefile error: {e}]")
        return
    if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        print("  no resource directory at all")
        return
    found_any = False
    types = []
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        type_id = entry.id if entry.id is not None else entry.struct.Id
        type_name = entry.name.__str__() if entry.name else str(type_id)
        types.append(type_name)
        if type_id in (RT_FONT, RT_FONTDIR):
            found_any = True
            print(f"    *** FONT RESOURCE FOUND: type={type_name} ***")
    print(f"  resource types present: {types}")
    if not found_any:
        print("  (no RT_FONT / RT_FONTDIR entries)")


def scan_raw_sfnt(path: Path):
    data = path.read_bytes()
    filesize = len(data)
    real_hits = []
    for magic in SFNT_MAGICS:
        start = 0
        while True:
            idx = data.find(magic, start)
            if idx == -1:
                break
            tags = validate_sfnt(data, idx, filesize)
            if tags is not None:
                real_hits.append((idx, magic, tags))
            start = idx + 1
    print(f"  strictly-validated real sfnt hits: {len(real_hits)}")
    for off, magic, tags in real_hits[:40]:
        print(f"    @0x{off:x} magic={magic!r} tables={tags}")


for name in TARGETS:
    p = GAME / name
    if not p.exists():
        print(f"=== {name} : MISSING ===")
        continue
    print(f"=== {name} ({p.stat().st_size:,} bytes) ===")
    scan_pe_resources(p)
    scan_raw_sfnt(p)
    print()
