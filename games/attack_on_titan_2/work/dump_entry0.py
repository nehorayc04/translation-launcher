"""Dump entry 0 (and nearby candidates) of every REGION archive fully, using the
FIXED decompressor + group-table awareness, to see if the main-menu strings live
there but were previously cut off by the truncation bug or hidden inside a
nested group table."""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import LinkData, MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
TARGETS = {
    "REGION_EU": GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EU.BIN",
    "REGION_EU.he_backup": GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EU.BIN.he_backup",
    "REGION_EDEN_EU": GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
}

MENU_WORDS = ["Story Mode", "Another Mode", "Character Episode Mode",
              "Territory Recovery Mode", "Gallery", "System", "Exit", "Manual"]

def raw_bytes(path, idx):
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    assert code == MAGIC
    eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + idx * 16)
    start = eo * mult
    raw = data[start:start+csize]
    if dsize == 0:
        return raw, dsize
    return decompress_blocks(raw[8:], dsize), dsize

def dump_group_or_table(content, label):
    if is_datatable(content):
        blobs = parse_datatable(content)
        strs = [read_cstring(b) if b is not None else None for b in blobs]
        print(f"  [{label}] flat DataTable, {len(strs)} strings")
        return strs
    # try group table: u32 count + count*u32 offsets into same buffer
    if len(content) < 4:
        return []
    (count,) = struct.unpack_from("<I", content, 0)
    if count == 0 or count > 100000 or 4 + count*4 > len(content):
        print(f"  [{label}] not a datatable and not a plausible group table (count={count}, len={len(content)})")
        return []
    offsets = struct.unpack_from(f"<{count}I", content, 4)
    if any(o >= len(content) or o < 0 for o in offsets):
        print(f"  [{label}] not a datatable and not a plausible group table (bad offsets)")
        return []
    print(f"  [{label}] GROUP table, {count} nested tables")
    all_strs = []
    for gi, off in enumerate(offsets):
        sub = content[off:]
        if is_datatable(sub):
            blobs = parse_datatable(sub)
            strs = [read_cstring(b) if b is not None else None for b in blobs]
            all_strs.extend(strs)
            # print a sample
        else:
            pass
    return all_strs

for name, path in TARGETS.items():
    if not path.exists():
        print(f"=== {name}: MISSING ===")
        continue
    print(f"=== {name} ===")
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    print(f"  files={files}")
    # scan first 20 entries plus any entry whose raw bytes contain b"Story" or b"Gallery"
    candidates = set(range(0, min(20, files)))
    for i in range(files):
        eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + i * 16)
        start = eo * mult
        raw = data[start:start+csize]
        if b"Gallery" in raw or b"Story Mode" in raw or b"Territory" in raw:
            candidates.add(i)
    for idx in sorted(candidates):
        try:
            content, dsize = raw_bytes(path, idx)
        except Exception as e:
            print(f"  entry {idx}: decode error {e}")
            continue
        found = [w for w in MENU_WORDS if w.encode() in content]
        if found or idx < 5:
            print(f" entry {idx} (dsize={dsize}, len={len(content)}): menu words found = {found}")
        if found:
            strs = dump_group_or_table(content, f"entry {idx}")
            for w in MENU_WORDS:
                hits = [s for s in strs if s and w in s]
                if hits:
                    print(f"      '{w}' -> {hits[:5]}")
    print()
