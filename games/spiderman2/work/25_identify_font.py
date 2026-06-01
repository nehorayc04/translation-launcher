"""Identify the OTF I extracted (read its 'name' table) + validate the 241 TTF
candidates with a stricter check (4+ known tables, sane numTables, etc.)."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
EXE  = os.path.join(GAME, "Spider-Man2.exe")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "exe_fonts")

# 1) Read name table of the extracted OTF
OTF_PATH = os.path.join(OUT, "exe_otf_188404920.otf")
otf = open(OTF_PATH, "rb").read()
print(f"[*] OTF: {len(otf)} bytes")

# Find 'name' table record in the OTF header
num_tables = struct.unpack(">H", otf[4:6])[0]
name_off = name_len = None
for k in range(num_tables):
    rec = otf[12 + k*16 : 12 + (k+1)*16]
    tag = rec[:4]
    off = struct.unpack(">I", rec[8:12])[0]
    ln = struct.unpack(">I", rec[12:16])[0]
    if tag == b"name":
        name_off = off
        name_len = ln
        break
print(f"[*] name table at off={name_off} len={name_len}")

if name_off:
    n = otf[name_off:name_off+name_len]
    fmt, count, string_off = struct.unpack(">HHH", n[:6])
    print(f"[*] name fmt={fmt} count={count} stringOffset={string_off}")
    strings_blob = n[string_off:]
    for i in range(count):
        rec = n[6 + i*12 : 6 + (i+1)*12]
        plat, enc, lang, nid, slen, soff = struct.unpack(">HHHHHH", rec)
        s = strings_blob[soff:soff+slen]
        # Decode based on platform/encoding
        try:
            if plat == 3:    # Windows
                txt = s.decode("utf-16-be", "replace")
            elif plat == 1:  # Mac
                txt = s.decode("mac_roman", "replace")
            else:
                txt = s.decode("utf-8", "replace")
        except Exception:
            txt = s.hex()
        NAME_IDS = {0:"Copyright",1:"Family",2:"Subfamily",3:"UniqueID",4:"FullName",
                    5:"Version",6:"PostScript",7:"Trademark",8:"Manufacturer",9:"Designer",
                    16:"PreferredFamily",17:"PreferredSubfamily",256:"Sample"}
        nid_name = NAME_IDS.get(nid, str(nid))
        if nid in (1, 2, 4, 6, 8, 9, 16, 17) and plat == 3 and len(txt) < 200:
            print(f"  name[{nid_name:<18}] plat={plat} enc={enc} lang={lang}: {txt!r}")

# 2) Validate TTF candidates - run only on the first 50
print()
print("=== validating TTF candidates (first 50) ===")
data = open(EXE, "rb").read()
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
    if len(TTF_OFFS) > 50: break

KNOWN_OTF_TABLES = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name",
                    b"post", b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS",
                    b"GSUB", b"hmtx", b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

real_fonts = []
for j in TTF_OFFS:
    if j + 12 >= len(data): continue
    nt = struct.unpack(">H", data[j+4:j+6])[0]
    valid = 0
    extents = []
    for k in range(nt):
        rec = data[j+12 + k*16 : j+12 + (k+1)*16]
        if len(rec) < 16: break
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag):
            valid = 0; break
        off = struct.unpack(">I", rec[8:12])[0]
        ln  = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN_OTF_TABLES:
            valid += 1
    if valid >= 5 and extents:
        max_end = max(o+l for _, o, l in extents)
        if 30_000 < max_end < 50_000_000:
            real_fonts.append((j, nt, valid, max_end))
            print(f"  [{j:>10}] TTF: numTables={nt} known={valid} totalLen={max_end}")
            # extract!
            font = data[j : j+max_end]
            outp = os.path.join(OUT, f"exe_ttf_{j}.ttf")
            with open(outp, "wb") as wf:
                wf.write(font)

print()
print(f"[+] {len(real_fonts)} real TTF fonts found in exe")
print(f"[+] all extracted to {OUT}")
print()
print("=== final font inventory ===")
for f in sorted(os.listdir(OUT)):
    sz = os.path.getsize(os.path.join(OUT, f))
    print(f"  {sz:>10}  {f}")
