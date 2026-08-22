"""Scan the AoT2 executables for embedded font resources (Win32 RT_FONT /
RT_FONTDIR PE resources) AND for raw sfnt magic bytes anywhere in the file
(covers fonts embedded outside the formal resource table, e.g. appended
data or a custom loader). Read-only.
"""
import struct
import sys
from pathlib import Path

import pefile

GAME = Path("F:/Games/Attack on Titan 2")
TARGETS = ["AOT2_EU.exe", "AOT2_AS.exe", "AOT2_JP.exe", "Launcher.exe"]

SFNT_MAGICS = [b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"]

RT_FONT = 8
RT_FONTDIR = 7


def scan_pe_resources(path: Path):
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
    except Exception as e:
        print(f"  [pefile error: {e}]")
        return
    if not hasattr(pe, "DIRECTORY_ENTRY_RESOURCE"):
        print("  no resource directory at all")
        return
    found_any = False
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        type_id = entry.id if entry.id is not None else entry.struct.Id
        type_name = entry.name.__str__() if entry.name else str(type_id)
        print(f"  resource type: {type_name}")
        if type_id in (RT_FONT, RT_FONTDIR):
            found_any = True
            print(f"    *** FONT RESOURCE FOUND: type={type_name} ***")
    if not found_any:
        print("  (no RT_FONT / RT_FONTDIR entries)")


def scan_raw_sfnt(path: Path):
    data = path.read_bytes()
    hits = []
    for magic in SFNT_MAGICS:
        start = 0
        while True:
            idx = data.find(magic, start)
            if idx == -1:
                break
            hits.append((magic, idx))
            start = idx + 1
    print(f"  raw sfnt-magic scan: {len(hits)} candidate hit(s)")
    # validate a sample with fontTools
    if hits:
        from fontTools.ttLib import TTFont
        import io
        validated = 0
        for magic, off in hits[:200]:
            try:
                f = TTFont(io.BytesIO(data[off:]), lazy=True, fontNumber=0)
                tables = list(f.reader.tables.keys())
                if len(tables) >= 3:
                    validated += 1
                    print(f"    candidate @0x{off:x} magic={magic!r}: {len(tables)} tables -> {tables[:8]}")
            except Exception:
                pass
        print(f"  -> {validated} of {min(len(hits),200)} sampled hits look like REAL fonts")


for name in TARGETS:
    p = GAME / name
    if not p.exists():
        print(f"=== {name} : MISSING ===")
        continue
    print(f"=== {name} ({p.stat().st_size:,} bytes) ===")
    scan_pe_resources(p)
    scan_raw_sfnt(p)
    print()
