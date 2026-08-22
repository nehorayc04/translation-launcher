import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
EDEN = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN"

needle = "（指示）Eliminate [r][0:PARTY][/]!"
data = EDEN.read_bytes()
code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
for i in range(files):
    eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + i * 16)
    if csize == 0:
        continue
    start = eo * mult
    raw = data[start:start+csize]
    try:
        c = raw if dsize == 0 else decompress_blocks(raw[8:], dsize)
    except Exception:
        continue
    if needle.encode() in c:
        blobs = parse_datatable(c) if is_datatable(c) else None
        n = len(blobs) if blobs else "N/A"
        print(f"HIT: EDEN entry {i}, size={len(c)}, string-count={n}")
