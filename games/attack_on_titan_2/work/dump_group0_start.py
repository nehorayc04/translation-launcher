import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import decompress_blocks, parse_datatable, read_cstring, MAGIC

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
path = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EU.BIN"

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

content = raw_content(path, 0)
offs = group_offsets(content)
sub = content[offs[0]:]
blobs = parse_datatable(sub)
strs = [read_cstring(b) if b is not None else None for b in blobs]
for i in range(0, 40):
    print(f"  [{i}] {strs[i]!r}")
