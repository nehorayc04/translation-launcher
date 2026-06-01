"""Confirm: does variant_18 (Arabic) embed an OTF font?
If yes — find the offset, length, and extract it for inspection."""
import os, sys, struct, io
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.types.dat1

SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "loc_variants", "variant_18_idx1276510.localization")
data = open(SRC, "rb").read()
print(f"[*] variant_18: {len(data)} bytes")

# Find OTTO occurrences
otto_offs = []
i = 0
while True:
    j = data.find(b"OTTO", i)
    if j < 0: break
    otto_offs.append(j)
    i = j + 4
print(f"[*] OTTO signatures: {len(otto_offs)} at offsets {otto_offs[:20]}")

# TTF magic (\x00\x01\x00\x00) too
ttf_offs = []
i = 0
while True:
    j = data.find(b"\x00\x01\x00\x00", i)
    if j < 0: break
    if j + 12 < len(data):
        num_tables = struct.unpack(">H", data[j+4:j+6])[0]
        tag = data[j+12:j+16]
        if 4 <= num_tables <= 40 and len(tag) == 4 and all(0x20 <= b <= 0x7E for b in tag):
            ttf_offs.append((j, num_tables, tag))
    i = j + 4
    if len(ttf_offs) > 30: break
print(f"[*] TTF signatures (validated): {len(ttf_offs)} -> {ttf_offs[:10]}")

# Both: ttcf?
ttcf_offs = []
i = 0
while True:
    j = data.find(b"ttcf", i)
    if j < 0: break
    ttcf_offs.append(j)
    i = j + 4
print(f"[*] TTC (ttcf) signatures: {len(ttcf_offs)} at {ttcf_offs[:5]}")

# Now: parse variant_18 as DAT1 (skip 36-byte prefix) and see which section
# any OTTO occurrence sits inside.
payload = data[36:]
dat1 = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
secs = sorted([(sh.tag, sh.offset, sh.size) for sh in dat1.header.sections], key=lambda x: x[1])
print()
print("=== sections (sorted by offset) ===")
for tag, off, size in secs:
    print(f"  tag=0x{tag:08X}  off={off:8}  size={size:8}  end={off+size:8}")

# For each OTTO offset, find which section it falls within
print()
print("=== OTTO -> section attribution (offsets are in the raw file, so subtract 36) ===")
for off in otto_offs:
    in_payload = off - 36
    for tag, sec_off, sec_size in secs:
        if sec_off <= in_payload < sec_off + sec_size:
            rel = in_payload - sec_off
            print(f"  OTTO at file_off={off:8}  (payload_off={in_payload:8}) -> section 0x{tag:08X}  rel={rel}")
            break
    else:
        print(f"  OTTO at file_off={off:8} not in any section")

# Try to read OTTO as a real OTF header at first occurrence (with header validation)
print()
print("=== validate OTTO as OpenType ===")
if otto_offs:
    j = otto_offs[0]
    # OpenType OTTO header:
    # u32 magic = 'OTTO'  (already matched)
    # u16 numTables
    # u16 searchRange
    # u16 entrySelector
    # u16 rangeShift
    # then numTables * 16-byte table records (tag, checksum, offset, length)
    if j + 12 < len(data):
        num_tables = struct.unpack(">H", data[j+4:j+6])[0]
        print(f"  OTTO[{j}]: numTables={num_tables}")
        if 4 <= num_tables <= 40:
            # Walk table records
            records_start = j + 12
            table_extents = []
            for k in range(num_tables):
                rec = data[records_start + k*16 : records_start + (k+1)*16]
                if len(rec) < 16: break
                tag = rec[:4]
                offset = struct.unpack(">I", rec[8:12])[0]
                length = struct.unpack(">I", rec[12:16])[0]
                tag_str = tag.decode('ascii', 'replace') if all(0x20<=b<=0x7E for b in tag) else repr(tag)
                table_extents.append((tag_str, offset, length))
                print(f"   table[{k:2}] tag={tag_str!r:<10} font_offset={offset:8} length={length}")
            if table_extents:
                # Total font length estimate: max(offset+length)
                max_end = max(o + l for _, o, l in table_extents)
                # font is from j .. j+max_end (since table offsets are relative to start of font)
                print(f"  estimated font total length: {max_end} bytes (font ends at file offset {j+max_end})")
