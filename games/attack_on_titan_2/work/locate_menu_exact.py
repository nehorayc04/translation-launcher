"""Precisely locate each main-menu label as an EXACT string value inside the
group-table structure of entry 0, across REGION_EU and REGION_EDEN_EU."""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
TARGETS = {
    "REGION_EU": GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EU.BIN",
    "REGION_EDEN_EU": GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
}
MENU_WORDS = ["Story Mode", "Another Mode", "Character Episode Mode",
              "Territory Recovery Mode", "Gallery", "System", "Exit", "Manual"]

def raw_content(path, idx):
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + idx * 16)
    start = eo * mult
    raw = data[start:start+csize]
    if dsize == 0:
        return raw
    return decompress_blocks(raw[8:], dsize)

def group_offsets(content):
    (count,) = struct.unpack_from("<I", content, 0)
    return struct.unpack_from(f"<{count}I", content, 4)

for name, path in TARGETS.items():
    print(f"=== {name} entry 0 ===")
    content = raw_content(path, 0)
    offs = group_offsets(content)
    for gi, off in enumerate(offs):
        sub = content[off:]
        if not is_datatable(sub):
            print(f"  group {gi} @off {off}: NOT a datatable, skip")
            continue
        blobs = parse_datatable(sub)
        strs = [read_cstring(b) if b is not None else None for b in blobs]
        for si, s in enumerate(strs):
            if s is not None and s.strip() in MENU_WORDS:
                print(f"  EXACT: group {gi} string {si} = {s!r}")
        # also print total count for context
        print(f"  group {gi}: {len(strs)} strings")
    print()
