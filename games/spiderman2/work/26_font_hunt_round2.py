"""Round 2 font hunt — three vectors in one pass:
  A. Validate the 3 OTTO hits in d/config as real fonts
  B. Search Spider-Man2.exe for font-registration API names + nearby strings
  C. Look at d/conduit's smallest+largest assets for CSS/HTML content
"""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
EXE  = os.path.join(GAME, "Spider-Man2.exe")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "round2")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

KNOWN_OTF_TABLES = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name",
                    b"post", b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS",
                    b"GSUB", b"hmtx", b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

def validate_font_at(data, j, magic):
    """Return (numTables, knownCount, totalLen, extents) if valid; None otherwise."""
    if j + 12 >= len(data): return None
    if data[j:j+4] != magic: return None
    nt = struct.unpack(">H", data[j+4:j+6])[0]
    if not (4 <= nt <= 40): return None
    extents = []
    known = 0
    for k in range(nt):
        rec = data[j+12 + k*16 : j+12 + (k+1)*16]
        if len(rec) < 16: return None
        tag = rec[:4]
        if not all(0x20<=b<=0x7E for b in tag): return None
        off = struct.unpack(">I", rec[8:12])[0]
        ln  = struct.unpack(">I", rec[12:16])[0]
        extents.append((tag, off, ln))
        if tag in KNOWN_OTF_TABLES:
            known += 1
    if known < 4: return None
    return (nt, known, max(o+l for _, o, l in extents), extents)

def scan_for_fonts(data, label):
    found = []
    # OTTO
    i = 0
    while True:
        j = data.find(b"OTTO", i)
        if j < 0: break
        res = validate_font_at(data, j, b"OTTO")
        if res:
            found.append((j, b"OTTO", res))
        i = j + 4
    # TTF magic
    i = 0
    while True:
        j = data.find(b"\x00\x01\x00\x00", i)
        if j < 0: break
        res = validate_font_at(data, j, b"\x00\x01\x00\x00")
        if res:
            found.append((j, b"TTF", res))
        i = j + 4
    # TTC magic
    i = 0
    while True:
        j = data.find(b"ttcf", i)
        if j < 0: break
        if j+4 < len(data):
            # ttcf header has version (4 bytes), numFonts (4 bytes), offsets
            v = struct.unpack(">I", data[j+4:j+8])[0]
            if v in (0x00010000, 0x00020000):
                # numFonts at j+8
                nfonts = struct.unpack(">I", data[j+8:j+12])[0]
                if 1 <= nfonts <= 50:
                    found.append((j, b"TTC", (None, None, None, nfonts)))
        i = j + 4
    print(f"  {label}: {len(found)} validated font(s)")
    for j, magic, info in found[:20]:
        print(f"    [{j:>10}]  {magic!r}  info={info[:3] if info[0] else info}")
    return found

# ---- A: d/config validation ----
print("=== A: d/config ===")
cfg = open(os.path.join(GAME, "d", "config"), "rb").read()
found_cfg = scan_for_fonts(cfg, "d/config")
# extract any
for j, magic, info in found_cfg:
    if info[2] and 30_000 < info[2] < 50_000_000:
        font = cfg[j:j+info[2]]
        outp = os.path.join(OUT, f"config_{magic.decode('ascii','replace').strip()}_{j}.font")
        with open(outp, "wb") as wf: wf.write(font)
        print(f"    [+] extracted {outp}")

# ---- B: exe font-registration & loader strings ----
print()
print("=== B: exe for font-registration APIs and resource paths ===")
exe = open(EXE, "rb").read()
api_tokens = [
    b"AddFontMemResource", b"AddFontMemResourceEx",
    b"CreateFontIndirect", b"GetFontData",
    b"FT_New_Memory_Face", b"FT_New_Face", b"FreeType",
    b"DWriteCreateFactory", b"CreateFontFaceFromMemory",
    b"RegisterFont", b"RegisterFontFace", b"RegisterFontFaceFromMemory",
    b"LoadFont", b"LoadFontFromFile", b"LoadFontFromMemory",
    b"cohtml::Library", b"cohtml::System",
    b"FontInfo", b"FontConfig", b"FontFaceData",
    b"DirectWrite",
    # Insomniac specific guesses:
    b"InsoFont", b"SimsFont",
    # CSS in exe (maybe inline stylesheets):
    b"@font-face", b"font-family:",
    # potential UI resource paths:
    b"ui/fonts/", b"ui/font/", b"data/fonts/", b"resources/fonts/",
    b"uiresources/fonts/", b"uiresources/font/", b"uiresources/css/",
    b"uiresources/main", b"uiresources/style",
]
for t in api_tokens:
    c = exe.count(t)
    if c:
        # Show first 3 occurrences with context
        i = 0; shown = 0
        while shown < 3:
            j = exe.find(t, i)
            if j < 0: break
            start = max(0, j-50)
            end = min(len(exe), j+150)
            chunk = exe[start:end]
            txt = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in chunk)
            print(f"  {t!r:<40} [{j:>9}] ...{txt}...")
            shown += 1
            i = j + 1

# ---- C: d/conduit asset content scan ----
print()
print("=== C: d/conduit assets for CSS/HTML/font-related strings ===")
with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
archs = toc.get_archives_section()
conduit_arch = None
for i, a in enumerate(archs.archives):
    name = bytes(a.filename).split(b"\x00")[0].decode("ascii")
    if name.endswith("conduit"):
        conduit_arch = i
        break

# Get all conduit entries
conduit_entries = []
aid_section = toc.get_assets_section()
for idx in range(len(aid_section.ids)):
    e = toc.get_asset_entry_by_index(idx)
    if e is not None and e.archive == conduit_arch:
        conduit_entries.append(e)
# Sort by size descending — bigger assets more likely to be UI bundles
conduit_entries.sort(key=lambda e: -e.size)
print(f"  {len(conduit_entries)} entries in conduit. Top-10 by size:")
font_tokens = [b"@font-face", b"font-family", b"Noto", b"NotoSans", b".ttf", b".otf",
               b"OTTO", b"<style", b"<html", b"<body", b"font-family:"]
for e in conduit_entries[:10]:
    try:
        d = bytes(toc.extract_asset(e))[36:]
    except Exception as ex:
        continue
    hits_str = []
    for t in font_tokens:
        c = d.count(t)
        if c:
            hits_str.append(f"{t.decode('ascii','replace')}={c}")
    print(f"    idx={e.index:>8} size={e.size:>9}  hits: {hits_str if hits_str else '(none)'}")
    # If big hits, save it for inspection
    if hits_str:
        outp = os.path.join(OUT, f"conduit_{e.index}.bin")
        with open(outp, "wb") as wf: wf.write(d)
        print(f"      saved -> {outp}")
