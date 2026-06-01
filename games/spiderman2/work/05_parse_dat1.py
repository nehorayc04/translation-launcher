"""Strip 36-byte AssetEntry header and parse the .localization payload as DAT1.
List all sections with tags+sizes. Find which sections hold UTF-8 string blobs."""
import os, sys, io, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib, dat1lib.types.dat1

LOCS = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants")
fns = sorted(os.listdir(LOCS))
print(f"[+] {len(fns)} variant files")

# Pick variant_00 first
target = os.path.join(LOCS, fns[0])
raw = open(target, "rb").read()
print(f"[*] {fns[0]}: {len(raw)} bytes")

# Skip the 36-byte AssetEntry.header prefix
payload = raw[36:]
print(f"[*] payload after header: {len(payload)} bytes, first8={payload[:8].hex(' ')}")

# Parse as DAT1
dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
print(f"[+] sections: {len(dat1.header.sections)}")

# Tag → name lookup
TAG_NAMES = {
    0x06A58050: "Loc.x06A58050",
    0x0CD2CFE9: "Loc.SortedIndexes",
    0xA4EA55B2: "Loc.TagOffsets",
    0xB0653243: "Loc.Flags",
    0xC43731B5: "Loc.SortedHashes",
    0xF80DEEB4: "Loc.TextOffsets",
}

print()
print("=== sections ===")
for i, sh in enumerate(dat1.header.sections):
    name = TAG_NAMES.get(sh.tag, "")
    # Pull bytes for this section
    raw_sec = dat1._raw_data[sh.offset:sh.offset+sh.size] if hasattr(dat1, '_raw_data') else None
    # Try to read directly from payload using offsets
    sec_bytes = payload[sh.offset + dat1.header.size_offset if hasattr(dat1.header,'size_offset') else sh.offset:][:sh.size] if False else None

    sec_obj = dat1.sections[i]
    sec_class = type(sec_obj).__name__ if sec_obj is not None else "None"
    print(f"  [{i:2}] tag=0x{sh.tag:08X}  off={sh.offset:8}  size={sh.size:8}  name={name:25}  cls={sec_class}")

# Try to extract the raw blob for each section directly from payload
# DAT1 sections are usually offset relative to a base after the header
print()
print("=== raw bytes preview per section (first 64) ===")
for i, sh in enumerate(dat1.header.sections):
    # The section offsets in DAT1 are relative to start of file (within `payload`)
    sec_data = payload[sh.offset : sh.offset + min(sh.size, 64)]
    print(f"  [{i:2}] off={sh.offset:8} sz={sh.size:8}  hex: {sec_data.hex(' ')[:80]}  txt: {sec_data[:32].decode('utf-8', 'replace')!r}")
