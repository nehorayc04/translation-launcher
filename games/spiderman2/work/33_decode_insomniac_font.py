"""Insomniac's 'font' assets have an 8-byte custom header followed by OTF table
records. Walk the records, count valid tables, then reconstruct a standard
OTF file by writing a proper 12-byte sfnt header in front of the records.

Format hypothesis:
  bytes 0..3: u32 BE — total size or end-offset (?)
  bytes 4..7: u32 BE — ?
  bytes 8+:   16-byte OTF table records (tag, checksum, offset, length)

We rebuild as: magic + numTables + searchRange + entrySelector + rangeShift
              + (records) + (data already in place if offsets are absolute)
"""
import os, sys, struct, math
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC  = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_big_assets")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "reconstructed_otf")
os.makedirs(OUT, exist_ok=True)

# Reasonable OTF table tags
VALID_TAGS = {b"BASE", b"CFF ", b"CFF2", b"CPAL", b"COLR", b"CBDT", b"CBLC",
              b"DSIG", b"EBDT", b"EBLC", b"EBSC", b"FFTM", b"GDEF", b"GPOS",
              b"GSUB", b"HVAR", b"JSTF", b"LTSH", b"MERG", b"MVAR", b"OS/2",
              b"PCLT", b"STAT", b"SVG ", b"VDMX", b"VORG", b"VVAR",
              b"acnt", b"ankr", b"avar", b"bdat", b"bhed", b"bloc", b"bsln",
              b"cmap", b"cvar", b"cvt ", b"fdsc", b"feat", b"fmtx", b"fond",
              b"fpgm", b"fvar", b"gasp", b"gcid", b"glyf", b"gvar", b"hdmx",
              b"head", b"hhea", b"hmtx", b"just", b"kern", b"lcar", b"loca",
              b"ltag", b"maxp", b"meta", b"mort", b"morx", b"name", b"opbd",
              b"post", b"prep", b"prop", b"sbix", b"trak", b"vhea", b"vmtx",
              b"xref", b"Zapf"}

def reconstruct(path, out_path):
    data = open(path, "rb").read()
    print(f"\n=== {os.path.basename(path)}  ({len(data)} bytes) ===")
    print(f"  prefix 8 bytes: {data[:8].hex(' ')}")

    # Walk table records starting at byte 8 until we hit a non-tag
    records = []
    pos = 8
    while pos + 16 <= len(data):
        tag = data[pos:pos+4]
        if tag not in VALID_TAGS:
            # check if it's a tag-like ASCII at least
            if not all(0x20 <= b <= 0x7E for b in tag):
                break
            # could be a valid tag we don't know — accept if printable
            print(f"  unknown tag at byte {pos}: {tag!r}, stopping")
            break
        cks, off, ln = struct.unpack(">III", data[pos+4:pos+16])
        records.append((tag, cks, off, ln))
        pos += 16

    if not records:
        print("  no table records found")
        return None

    print(f"  found {len(records)} table records:")
    for tag, cks, off, ln in records:
        end = off + ln
        in_bounds = "OK" if end <= len(data) else f"OUT-OF-BOUNDS (end={end})"
        print(f"    {tag.decode('ascii'):<6}  off={off:>9}  len={ln:>9}  end={end:>9}  {in_bounds}")

    # Detect magic: if CFF present → OTTO; if glyf → TTF
    has_cff = any(t == b"CFF " for t, _, _, _ in records)
    has_cff2 = any(t == b"CFF2" for t, _, _, _ in records)
    has_glyf = any(t == b"glyf" for t, _, _, _ in records)
    magic = b"OTTO" if (has_cff or has_cff2) else b"\x00\x01\x00\x00"
    print(f"  magic = {magic!r}  (CFF={has_cff} CFF2={has_cff2} glyf={has_glyf})")

    # Compute searchRange = 16 * (2^floor(log2(numTables)))
    nt = len(records)
    log2 = int(math.log2(nt))
    sr = 16 * (1 << log2)
    es = log2
    rs = nt * 16 - sr

    # Build the standard 12-byte header + table records + table data
    # KEY question: are the table offsets in the original data ABSOLUTE (relative
    # to file start) or RELATIVE to start of table data area?
    # If absolute: we need to keep file bytes identical (just prepend 4 bytes
    # to shift everything? no — that breaks offsets).
    # Looking at the data: GPOS at offset 8 has its "offset" = 23,438,108 (for
    # the 23 MB file). So offsets ARE absolute relative to file start.
    # The 8-byte prefix is already part of the absolute coordinate system.
    # So when reconstructing, we replace the 8 prefix bytes with a 12-byte
    # standard header (4 magic + 8 sfnt fields).
    # That shifts all subsequent bytes by +4. We need to ADD 4 to every offset.

    new_records = []
    for tag, cks, off, ln in records:
        new_records.append((tag, cks, off + 4, ln))   # shift +4 for new 4-byte magic

    # Build header
    out = bytearray()
    out += magic
    out += struct.pack(">HHHH", nt, sr, es, rs)
    for tag, cks, off, ln in new_records:
        out += struct.pack(">4sIII", tag, cks, off, ln)
    out += b"\x00" * (4 + (8 + nt*16 - len(out)))  # pad to where original byte 8+nt*16 started, +4
    # Append rest of file from after the original table records
    original_data_start = 8 + nt*16
    # In standard OTF, table data area starts immediately after table records (12 + nt*16).
    # We want byte (12 + nt*16) of NEW file to correspond to byte (8 + nt*16) of OLD.
    # That means we shift everything past byte 8+nt*16 by +4. The records themselves we
    # already shifted offsets +4 above.
    # So write: 12-byte header + nt*16 records (already done) + 4 bytes pad + original data from offset (8+nt*16)
    out_full = bytearray()
    out_full += magic
    out_full += struct.pack(">HHHH", nt, sr, es, rs)
    for tag, cks, off, ln in new_records:
        out_full += struct.pack(">4sIII", tag, cks, off, ln)
    # Now we're at position 12 + nt*16. Original data starts at 8 + nt*16.
    # We added 4 extra bytes (header magic) to shift everything. So we copy
    # original bytes from byte (8+nt*16) onward, but we ALSO need to NOT overwrite
    # any region that should be different. Actually since offsets were shifted +4,
    # the data should be written 4 bytes later than it was originally.
    # Simplest: prepend 4 bytes to the entire original file (replacing the first 4
    # bytes of the 8-byte prefix with the OTF header magic).
    # Final formula: new_file = magic + struct.pack(headers...) + original_records_shifted + remaining_data
    # Where remaining_data = data[8+nt*16:]
    out_full += data[8 + nt*16:]
    # Header check — our out_full so far is magic(4) + sfntheader(8) + nt*16 records + data
    # That's 12 + nt*16 + len(remaining) = 12 + nt*16 + (len(data) - 8 - nt*16) = 4 + len(data)
    expected = 4 + len(data)
    actual = len(out_full)
    print(f"  reconstructed size: {actual} (expected {expected})  delta={actual-expected}")

    with open(out_path, "wb") as f: f.write(out_full)
    print(f"  saved -> {out_path}")
    return out_full

for fn in sorted(os.listdir(SRC)):
    if not fn.startswith("ui_") or "_font_" in fn or not fn.endswith(".bin"): continue
    src_path = os.path.join(SRC, fn)
    out_name = fn.replace(".bin", ".otf")
    out_path = os.path.join(OUT, out_name)
    reconstruct(src_path, out_path)

print()
print("=== inventory ===")
for f in sorted(os.listdir(OUT)):
    sz = os.path.getsize(os.path.join(OUT, f))
    print(f"  {sz:>10}  {f}")
