"""Stream-scan every DSAR archive in d/ for TTF/OTF signatures.
Once we find them we know which archive holds the font payload."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")

# Scan in small chunks since some archives are >1 GB. TTF magic is 4 bytes:
# \x00\x01\x00\x00 (TrueType) or "OTTO" (OpenType CFF) or "ttcf" (collection)
TTF_MAGICS = [b"\x00\x01\x00\x00", b"OTTO", b"ttcf"]

ARCHS = sorted(os.listdir(os.path.join(GAME, "d")))
# Skip the huge ones for the first pass — focus on UI-likely ones
PRIORITY = ["conduit", "config", "localization", "actor", "model_hero", "material"]
ARCHS_SORTED = PRIORITY + [a for a in ARCHS if a not in PRIORITY]

CHUNK = 16 * 1024 * 1024  # 16 MB at a time
MAX_HITS_PER_ARCH = 30

results = {}

for arch_name in ARCHS_SORTED[:8]:   # first 8 archives only (priority list)
    path = os.path.join(GAME, "d", arch_name)
    if not os.path.isfile(path): continue
    size = os.path.getsize(path)
    print(f"\n=== scanning d/{arch_name} ({size:>13} bytes) ===")
    hits = []
    with open(path, "rb") as f:
        pos = 0
        prev_tail = b""
        while pos < size:
            buf = prev_tail + f.read(CHUNK)
            for magic in TTF_MAGICS:
                start = 0
                while True:
                    j = buf.find(magic, start)
                    if j < 0: break
                    # TTF: next u16 = numTables (typically 5..30). Sanity check.
                    if magic == b"\x00\x01\x00\x00":
                        if j + 12 < len(buf):
                            num_tables = struct.unpack(">H", buf[j+4:j+6])[0]
                            if 4 <= num_tables <= 40:
                                # also: scan ahead for known TTF table tags
                                table_tags = buf[j+12:j+12+min(num_tables,5)*16]
                                # table tags are 4-byte ASCII like "cmap", "GSUB", "name", etc.
                                tag = table_tags[:4]
                                if tag and all(0x20<=b<=0x7E for b in tag):
                                    hits.append((pos+j, magic, num_tables, tag))
                    else:
                        hits.append((pos+j, magic, None, None))
                    if len(hits) >= MAX_HITS_PER_ARCH: break
                    start = j + 1
                if len(hits) >= MAX_HITS_PER_ARCH: break
            if len(hits) >= MAX_HITS_PER_ARCH: break
            prev_tail = buf[-3:]
            pos += len(buf) - 3
            if pos > 200 * 1024 * 1024:  # cap per-archive at 200 MB scanned
                print(f"  ... reached 200 MB scan cap")
                break
    if hits:
        results[arch_name] = hits
        print(f"  {len(hits)} TTF-like signatures found")
        for off, magic, ntab, tag in hits[:10]:
            tag_disp = repr(tag) if tag else '-'
            print(f"    offset={off:>10}  magic={magic!r}  numTables={ntab}  firstTag={tag_disp}")
    else:
        print("  no font signatures")

# Save a summary
print()
print("=== summary ===")
for a, h in results.items():
    print(f"  d/{a}: {len(h)} hits  -> first 3: {h[:3]}")
