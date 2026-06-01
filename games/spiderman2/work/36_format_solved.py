"""Hypothesis: ALL table offsets in Insomniac records are TRUE_offset + 36.
Verify by checking each table at offset (record_offset - 36)."""
import os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "games", "spiderman2", "extracted", "ui_big_assets", "ui_298871.bin")
data = open(SRC, "rb").read()

def validate_head(b):
    return b[:4] == bytes.fromhex("00010000") and b[12:16] == bytes.fromhex("5F0F3CF5")
def validate_hhea(b):
    # u32 version = 0x00010000
    return b[:4] == bytes.fromhex("00010000")
def validate_maxp(b):
    return b[:4] in (bytes.fromhex("00010000"), bytes.fromhex("00005000"))
def validate_os2(b):
    # u16 version = 0..5, u16 usWeightClass = 100..900
    v = struct.unpack(">H", b[:2])[0]
    wt = struct.unpack(">H", b[4:6])[0]
    return 0 <= v <= 5 and 100 <= wt <= 900
def validate_cmap(b):
    return b[:4] == bytes.fromhex("00000000") or b[:2] == bytes.fromhex("0000")  # version=0, count<=??
def validate_name(b):
    # format = 0 or 1, count plausible
    fmt = struct.unpack(">H", b[:2])[0]
    return fmt in (0, 1)
def validate_post(b):
    return b[:4] in (bytes.fromhex("00010000"), bytes.fromhex("00020000"),
                     bytes.fromhex("00025000"), bytes.fromhex("00030000"))

VALIDATORS = {b"head": validate_head, b"hhea": validate_hhea, b"maxp": validate_maxp,
              b"OS/2": validate_os2, b"cmap": validate_cmap, b"name": validate_name,
              b"post": validate_post}

records_off = 8
nt = 12
print("=== offset analysis ===")
for k in range(nt):
    rec = data[records_off + k*16 : records_off + (k+1)*16]
    tag = rec[:4]
    cks, off, ln = struct.unpack(">III", rec[4:16])
    delta_candidates = [-36, -32, -24, -16, -12, -8, -4, 0, +4, +8, +12, +16, +24, +32, +36]
    validator = VALIDATORS.get(tag)
    if not validator:
        print(f"  {tag!r:<8} record_off={off:>9}  (no validator)")
        continue
    matches = []
    for delta in delta_candidates:
        po = off + delta
        if 0 <= po < len(data) - 16:
            try:
                if validator(data[po:po+16]):
                    matches.append((delta, po))
            except: pass
    print(f"  {tag!r:<8} record_off={off:>9}  -> matching deltas: {matches}")

# Now reconstruct: write a standard OTF using the REAL offsets (record_offset - 36).
# That means we need to:
#   - prepend a 12-byte standard sfnt header
#   - keep the data area as-is (it already starts at byte 200 in OLD file)
#   - but adjust offsets: NEW_record_offset = REAL_offset + 12 - 8 = REAL_offset + 4
#       i.e. shift all offsets by +4
#       REAL_offset = record_offset - 36
#       NEW_record_offset = record_offset - 36 + 4 = record_offset - 32
print()
print("=== reconstruction with offset = record_offset - 32 ===")
import math
# Build records sorted by tag (sfnt convention)
records = []
for k in range(nt):
    rec = data[records_off + k*16 : records_off + (k+1)*16]
    tag = rec[:4]
    cks, off, ln = struct.unpack(">III", rec[4:16])
    real_off = off - 36
    new_off = real_off + 12      # shift to account for 12-byte standard header
    records.append((tag, cks, new_off, ln, real_off))

# Sort by tag (alphabetically) — sfnt convention
records.sort(key=lambda r: r[0])

# Detect magic
tags = {r[0] for r in records}
has_glyf = b"glyf" in tags
has_cff = b"CFF " in tags or b"CFF2" in tags
magic = b"\x00\x01\x00\x00" if has_glyf else (b"OTTO" if has_cff else b"\x00\x01\x00\x00")
nt2 = len(records)
log2 = int(math.log2(nt2))
sr = 16 * (1 << log2)
es = log2
rs = nt2 * 16 - sr

OUT = os.path.join(ROOT, "games", "spiderman2", "extracted", "reconstructed_otf", "ui_298871_v2.otf")
out = bytearray()
out += magic
out += struct.pack(">HHHH", nt2, sr, es, rs)
for tag, cks, new_off, ln, _ in records:
    out += struct.pack(">4sIII", tag, cks, new_off, ln)
# Append data area: original bytes from OLD byte 200 onward
# But our new file's data area starts at byte 12 + nt2*16 = 12 + 192 = 204
# OLD data area was at OLD byte 200. So we shift by +4.
out += data[200:]   # all data area bytes, in original order
print(f"reconstructed size: {len(out)}  (expected ~{len(data)+4})")
with open(OUT, "wb") as f: f.write(out)
print(f"saved -> {OUT}")

# Validate with fontTools
print()
print("=== fontTools validation ===")
from fontTools.ttLib import TTFont
try:
    font = TTFont(OUT, lazy=False)
    n = font['name']
    for r in n.names:
        if r.nameID in (1,2,4) and r.platformID == 3:
            try: print(f"  name[{r.nameID}]: {r.toUnicode()!r}")
            except: pass
    cm = font.getBestCmap()
    cps = set(cm.keys())
    print(f"  total mapped: {len(cps)}")
    def cov(lo,hi):
        n = sum(1 for cp in cps if lo<=cp<=hi); t = hi-lo+1
        return f"{n:>5}/{t:<5} ({100.0*n/t:5.1f}%)"
    for name, lo, hi in [("Latin",0x20,0x7F),("Hebrew",0x590,0x5FF),
                         ("Arabic",0x600,0x6FF),("Cyrillic",0x400,0x4FF),
                         ("CJK",0x4E00,0x9FFF),("Hangul",0xAC00,0xD7AF),
                         ("Thai",0xE00,0xE7F)]:
        print(f"  {name:<10}: {cov(lo,hi)}")
    font.close()
    print("  [+] LOADED SUCCESSFULLY")
except Exception as e:
    import traceback
    traceback.print_exc()
