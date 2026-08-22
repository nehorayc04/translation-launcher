import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
EDEN = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN"

def read_entry(path, idx):
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + idx * 16)
    start = eo * mult
    raw = data[start:start+csize]
    return raw if dsize == 0 else decompress_blocks(raw[8:], dsize)

for label, idx in [("story-intro equiv", 1639), ("battle-text equiv", 721)]:
    content = read_entry(EDEN, idx)
    blobs = parse_datatable(content)
    strs = [read_cstring(b) if b is not None else None for b in blobs]
    print(f"=== entry {idx} ({label}) — first 10 of {len(strs)} strings ===")
    for i, s in enumerate(strs[:10]):
        print(f"  [{i}] {s!r}")
    print()
