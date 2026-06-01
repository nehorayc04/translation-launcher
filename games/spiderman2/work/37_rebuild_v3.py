"""Final reconstruction with the CORRECT offset formula.

Insomniac layout:
  byte 0..7:           custom 8-byte prefix (ignored on read)
  byte 8..8+nt*16-1:   table records  (tag 4 / cks 4 / offset 4 / length 4)
  byte 8+nt*16..end:   data area starting at byte 8+nt*16

Record offsets are stored as (TRUE_OFFSET + 36), so:
  TRUE_OFFSET_in_old_file = record.offset - 36

To rebuild as standard OTF:
  - 12-byte sfnt header (magic + numTables + searchRange + entrySelector + rangeShift)
  - 16*nt records, with offset = TRUE_OFFSET + 4   (the extra 4 = standard 12-byte header vs Insomniac 8-byte)
  - data area copied verbatim from OLD byte 8+nt*16 onwards
"""
import os, sys, struct, math
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_big_assets")
OUT = os.path.join(ROOT, "games", "spiderman2", "extracted", "reconstructed_v3")
os.makedirs(OUT, exist_ok=True)

VALID_TAGS = {b"BASE",b"CFF ",b"CFF2",b"CPAL",b"COLR",b"DSIG",b"FFTM",b"GDEF",
              b"GPOS",b"GSUB",b"HVAR",b"JSTF",b"LTSH",b"MERG",b"MVAR",b"OS/2",
              b"PCLT",b"STAT",b"SVG ",b"VDMX",b"VORG",b"VVAR",b"avar",b"bdat",
              b"bhed",b"bloc",b"cmap",b"cvar",b"cvt ",b"feat",b"fpgm",b"fvar",
              b"gasp",b"gcid",b"glyf",b"gvar",b"hdmx",b"head",b"hhea",b"hmtx",
              b"just",b"kern",b"lcar",b"loca",b"ltag",b"maxp",b"meta",b"morx",
              b"mort",b"name",b"opbd",b"post",b"prep",b"prop",b"sbix",b"trak",
              b"vhea",b"vmtx",b"xref"}

def rebuild(src_path, out_path):
    data = open(src_path, "rb").read()
    # walk records starting at byte 8
    records = []
    pos = 8
    while pos + 16 <= len(data):
        tag = data[pos:pos+4]
        if tag not in VALID_TAGS:
            if not all(0x20<=b<=0x7E for b in tag): break
            print(f"  unknown tag {tag!r} at {pos} — stopping")
            break
        cks, off, ln = struct.unpack(">III", data[pos+4:pos+16])
        records.append((tag, cks, off, ln))
        pos += 16

    nt = len(records)
    data_area_start_old = 8 + nt * 16

    print(f"\n=== {os.path.basename(src_path)} ===")
    print(f"  numTables={nt}  data_area starts at byte {data_area_start_old}")

    # Compute true offsets (record - 36), then shift +4 for the new 12-byte header.
    new_records = []
    for tag, cks, off, ln in records:
        real_off = off - 36
        new_off = real_off + 4
        new_records.append((tag, cks, new_off, ln, real_off))

    # Sort alphabetically for sfnt convention
    new_records.sort(key=lambda r: r[0])

    # Detect magic
    tags = {r[0] for r in new_records}
    has_glyf = b"glyf" in tags
    has_cff = b"CFF " in tags or b"CFF2" in tags
    magic = b"OTTO" if has_cff else b"\x00\x01\x00\x00"

    log2 = int(math.log2(nt))
    sr = 16 * (1 << log2)
    es = log2
    rs = nt * 16 - sr

    out = bytearray()
    out += magic
    out += struct.pack(">HHHH", nt, sr, es, rs)
    for tag, cks, new_off, ln, real_off in new_records:
        out += struct.pack(">4sIII", tag, cks, new_off, ln)
    # Append data area — but skip the 8-byte prefix and the 16*nt records area
    out += data[data_area_start_old:]

    with open(out_path, "wb") as f: f.write(out)
    print(f"  wrote {len(out)} bytes -> {os.path.basename(out_path)}")

    # Verify with fontTools (with all errors caught)
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(out_path, lazy=False)
        # name
        n = font['name']
        names = {}
        for r in n.names:
            if r.nameID in (1,2,4,16) and r.platformID == 3:
                try: names[r.nameID] = r.toUnicode()
                except: pass
        print(f"  Family={names.get(1, '?')!r}  Subfamily={names.get(2, '?')!r}")
        # cmap
        cm = font.getBestCmap()
        cps = set(cm.keys())
        print(f"  cmap: {len(cps)} codepoints")
        def cov(lo, hi):
            n = sum(1 for cp in cps if lo<=cp<=hi); t = hi-lo+1
            return f"{n:>5}/{t:<5}"
        for name, lo, hi in [("Latin",0x20,0x7F),("Latin1",0x80,0xFF),
                             ("Hebrew",0x590,0x5FF),("Arabic",0x600,0x6FF),
                             ("Cyrillic",0x400,0x4FF),("Greek",0x370,0x3FF),
                             ("CJK",0x4E00,0x9FFF),("Hangul",0xAC00,0xD7AF),
                             ("Hiragana",0x3040,0x309F),("Katakana",0x30A0,0x30FF),
                             ("Thai",0xE00,0xE7F),("Devanagari",0x900,0x97F)]:
            cv = cov(lo, hi)
            if int(cv.split('/')[0]) > 0:
                print(f"    {name:<10} {cv}")
        font.close()
        return True
    except Exception as e:
        print(f"  fontTools error: {e}")
        return False

for fn in sorted(os.listdir(SRC)):
    if fn.startswith("ui_") and fn.endswith(".bin"):
        src = os.path.join(SRC, fn)
        out = os.path.join(OUT, fn.replace(".bin", ".otf"))
        rebuild(src, out)
