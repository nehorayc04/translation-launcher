"""Find the story-intro (entry 2424) and battle-text (entry 1056) equivalents
inside REGION_EDEN_EU.BIN by CONTENT, since Eden's entry indexing is totally
different (1645 vs 2438 total entries)."""
import sys, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from aot2_linkdata import MAGIC, decompress_blocks, is_datatable, parse_datatable, read_cstring

GAME_ROOT = Path(r"F:\Games\Attack on Titan 2")
EU_BAK = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EU.BIN.he_backup"
EDEN = GAME_ROOT / "LINKDATA" / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN"

def read_entry(path, idx):
    data = path.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    eo, epad, csize, dsize = struct.unpack_from("<IIII", data, 16 + idx * 16)
    start = eo * mult
    raw = data[start:start+csize]
    return raw if dsize == 0 else decompress_blocks(raw[8:], dsize)

def flat_strings(content):
    if not is_datatable(content):
        return None
    blobs = parse_datatable(content)
    return [read_cstring(b) if b is not None else None for b in blobs]

# get a few distinctive strings from the PRISTINE EU entries 2424 and 1056
for label, idx in [("story-intro (2424)", 2424), ("battle-text (1056)", 1056)]:
    content = read_entry(EU_BAK, idx)
    strs = flat_strings(content)
    if strs is None:
        print(f"{label}: not a flat datatable in EU backup?!")
        continue
    real = [s for s in strs if s and len(s) > 15 and s.strip('.').isascii() and any(c.islower() for c in s)]
    print(f"{label}: {len(strs)} strings total, sample distinctive ones:")
    for s in real[:8]:
        print(f"    {s!r}")
    print()

    # now search ALL entries of EDEN for one of these distinctive strings
    target_needle = real[0] if real else None
    if not target_needle:
        continue
    print(f"  searching EDEN for exact table containing: {target_needle!r}")
    data = EDEN.read_bytes()
    code, files, mult, pad = struct.unpack_from("<IIII", data, 0)
    found_any = False
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
        if target_needle.encode() in c:
            found_any = True
            estrs = flat_strings(c)
            n = len(estrs) if estrs else "N/A (not flat)"
            print(f"    HIT: EDEN entry {i}, size={len(c)}, string-count={n}")
    if not found_any:
        print(f"    NO MATCH found anywhere in EDEN for this exact text")
    print()
