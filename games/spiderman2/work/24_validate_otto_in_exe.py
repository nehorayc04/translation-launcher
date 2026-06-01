"""Validate the 3 OTTO signatures in Spider-Man2.exe — see if any is a real OTF
font (proper numTables and valid table records)."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
EXE  = os.path.join(GAME, "Spider-Man2.exe")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "exe_fonts")
os.makedirs(OUT, exist_ok=True)
data = open(EXE, "rb").read()
print(f"[*] exe = {len(data)} bytes")

# Find all OTTO + all validated TTF
OTTO_OFFS = []
i = 0
while True:
    j = data.find(b"OTTO", i)
    if j < 0: break
    OTTO_OFFS.append(j)
    i = j + 4
TTF_OFFS = []
i = 0
while True:
    j = data.find(b"\x00\x01\x00\x00", i)
    if j < 0: break
    if j + 12 < len(data):
        nt = struct.unpack(">H", data[j+4:j+6])[0]
        tag = data[j+12:j+16]
        if 4 <= nt <= 40 and all(0x20<=b<=0x7E for b in tag):
            TTF_OFFS.append(j)
    i = j + 4
print(f"[*] OTTO offsets: {OTTO_OFFS}")
print(f"[*] valid TTF-like offsets: {len(TTF_OFFS)} (showing first 5): {TTF_OFFS[:5]}")

KNOWN_OTF_TABLES = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name",
                    b"post", b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS",
                    b"GSUB", b"hmtx", b"vmtx", b"vhea"}

def validate(j, magic_name):
    if j + 12 >= len(data):
        return None
    num_tables = struct.unpack(">H", data[j+4:j+6])[0]
    if not (4 <= num_tables <= 40):
        return None
    table_extents = []
    valid_count = 0
    for k in range(num_tables):
        rec = data[j+12 + k*16 : j+12 + (k+1)*16]
        if len(rec) < 16: break
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag):
            return None
        checksum = struct.unpack(">I", rec[4:8])[0]
        offset = struct.unpack(">I", rec[8:12])[0]
        length = struct.unpack(">I", rec[12:16])[0]
        table_extents.append((tag, offset, length))
        if tag in KNOWN_OTF_TABLES:
            valid_count += 1
    if valid_count < 4:   # need at least 4 known tables
        return None
    max_end = max(o+l for _, o, l in table_extents)
    return (num_tables, valid_count, max_end, table_extents)

for j in OTTO_OFFS:
    res = validate(j, "OTTO")
    if res is None:
        print(f"  [{j}] OTTO: not a valid font")
        continue
    nt, vt, max_end, tables = res
    print(f"  [{j}] OTTO valid! numTables={nt}  knownTables={vt}  totalLen~{max_end}")
    for tag, off, ln in tables[:8]:
        print(f"     {tag!r:<10}  font_off={off:>8}  len={ln}")
    if 50000 < max_end < 50_000_000:   # sane font size
        font = data[j : j+max_end]
        outp = os.path.join(OUT, f"exe_otf_{j}.otf")
        with open(outp, "wb") as wf:
            wf.write(font)
        print(f"     [+] extracted to {outp} ({len(font)} bytes)")

for j in TTF_OFFS[:5]:
    res = validate(j, "TTF")
    if res is None:
        continue
    nt, vt, max_end, tables = res
    print(f"  [{j}] TTF valid! numTables={nt}  knownTables={vt}  totalLen~{max_end}")
    for tag, off, ln in tables[:8]:
        print(f"     {tag!r:<10}  font_off={off:>8}  len={ln}")
    if 50000 < max_end < 50_000_000:
        font = data[j : j+max_end]
        outp = os.path.join(OUT, f"exe_ttf_{j}.ttf")
        with open(outp, "wb") as wf:
            wf.write(font)
        print(f"     [+] extracted to {outp} ({len(font)} bytes)")
