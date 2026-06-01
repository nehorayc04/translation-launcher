"""Detect what transformation Insomniac applied to the OTF table bodies.

Tests (in order of cost):
  1. Is the head table magicNumber (0x5F0F3CF5) present anywhere in the file?
  2. Is it present XOR'd with a common 4-byte mask?
  3. Are TABLE BOUNDARIES reasonable in a standard OTF layout (data immediately
     after records)?
  4. Are the data bytes at the recorded offsets a recognizable transformation
     (delta encoding, byte reordering, RLE) of a known-shape head table?
"""
import os, sys, struct, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_big_assets", "ui_298871.bin")
data = open(SRC, "rb").read()
print(f"[*] working on ui_298871.bin ({len(data)} bytes)")

HEAD_MAGIC = bytes.fromhex("5F0F3CF5")    # head.magicNumber, exactly at head offset 12
HEAD_VERSION = bytes.fromhex("00010000")  # head[0:4] = version
TTF_SFNT = bytes.fromhex("00010000")
OTTO_SFNT = b"OTTO"

# 1. Is head magic present anywhere?
idx = data.find(HEAD_MAGIC)
print(f"\n[1] head.magicNumber (5F0F3CF5) found at file offset: {idx}")
if idx >= 0:
    # head table starts 12 bytes before magic
    h_off = idx - 12
    print(f"    -> head table would start at offset {h_off}")
    print(f"    bytes at h_off..h_off+24: {data[h_off:h_off+24].hex(' ')}")
    # Check if it makes sense as a head table
    if h_off >= 0:
        ver = data[h_off:h_off+4]
        fontRev = struct.unpack(">I", data[h_off+4:h_off+8])[0]
        print(f"    head.version = {ver.hex(' ')}  (should be 00 01 00 00)")
        print(f"    head.fontRevision = 0x{fontRev:08X}")

# 2. Search for XOR'd head.magicNumber with single-byte XOR keys
print(f"\n[2] Searching for XOR-encoded head.magicNumber (single-byte keys)")
for k in range(1, 256):
    needle = bytes(b ^ k for b in HEAD_MAGIC)
    idx = data.find(needle)
    if idx >= 0:
        print(f"    XOR key=0x{k:02X}: found at offset {idx}")
        # show context
        ctx = bytes(b ^ k for b in data[max(0,idx-12):idx+12])
        print(f"      decoded context: {ctx.hex(' ')}")

# 3. Check if any TABLE OFFSETS, treated as absolute and pointing into the file,
#    look like the data immediately precedes the standard 12-byte OTF header.
#    Standard layout: offset 12 to offset (12 + 16*N) is the records area, and
#    table data follows.
print(f"\n[3] Table layout analysis")
nt = 12
records_off = 8
records_size = nt * 16
# Walk records to print
for k in range(nt):
    rec = data[records_off + k*16 : records_off + (k+1)*16]
    tag = rec[:4]
    cks, off, ln = struct.unpack(">III", rec[4:16])
    print(f"  {tag!r:<8}  off={off:>9}  len={ln:>6}")

# 4. cmap table — does it have any recognizable byte pattern at its offset?
#    Standard cmap header: u16 version(=0), u16 num_subtables
print(f"\n[4] First bytes of each table at the stored offsets:")
for k in range(nt):
    rec = data[records_off + k*16 : records_off + (k+1)*16]
    tag = rec[:4]
    cks, off, ln = struct.unpack(">III", rec[4:16])
    if off + 16 > len(data):
        continue
    blob = data[off:off+16]
    print(f"  {tag!r:<8} @ {off:>9}:  {blob.hex(' ')}")

# 5. Check: if we treat offsets as 'address space starting AT byte 12 of a
#    standard OTF', then the data at OLD_offset corresponds to NEW_offset+12.
#    Try shifting backwards in time: maybe offsets actually point into the
#    UNTRIMMED original file. For each offset, also peek at byte (off-8),
#    (off-12), (off+8), (off+12) — see if any reveals OTF-shaped data.
print(f"\n[5] Probing offsets at +/-8 and +/-12 around each table record:")
for k in range(nt):
    rec = data[records_off + k*16 : records_off + (k+1)*16]
    tag = rec[:4]
    cks, off, ln = struct.unpack(">III", rec[4:16])
    if tag != b"head": continue
    print(f"  head record says off={off}, len={ln}")
    for shift in (-12, -8, -4, 0, 4, 8, 12):
        probe_off = off + shift
        if 0 <= probe_off < len(data) - 16:
            blob = data[probe_off:probe_off+16]
            looks_head = blob[:4] == HEAD_VERSION and blob[12:16] == HEAD_MAGIC
            marker = "  <-- VALID HEAD" if looks_head else ""
            print(f"   shift={shift:+3d}  off={probe_off:>9}  bytes={blob.hex(' ')}{marker}")

# 6. Same for cmap — look for "00 00 00 NN" near its stored offset
print(f"\n[6] Probing cmap and 'name' offsets")
for target_tag in (b"cmap", b"name"):
    for k in range(nt):
        rec = data[records_off + k*16 : records_off + (k+1)*16]
        if rec[:4] != target_tag: continue
        _, off, ln = struct.unpack(">III", rec[4:16])
        print(f"  {target_tag.decode()} record says off={off}, len={ln}")
        for shift in (-12, -8, -4, 0, 4, 8, 12):
            po = off + shift
            if 0 <= po < len(data) - 16:
                print(f"   shift={shift:+3d}  off={po:>9}  bytes={data[po:po+16].hex(' ')}")
