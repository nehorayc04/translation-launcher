"""Scan cohtml + Renoir DLLs for embedded OTF/TTF fonts (the validated kind),
and dump all paths that look like font references."""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "dll_fonts")
os.makedirs(OUT, exist_ok=True)

KNOWN = {b"CFF ", b"CFF2", b"head", b"hhea", b"maxp", b"name", b"post",
         b"OS/2", b"cmap", b"glyf", b"loca", b"GPOS", b"GSUB", b"hmtx",
         b"vmtx", b"vhea", b"DSIG", b"BASE", b"GDEF"}

def validate_otf(data, j):
    if data[j:j+4] != b"OTTO" and data[j:j+4] != b"\x00\x01\x00\x00": return None
    if j + 12 >= len(data): return None
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
        if tag in KNOWN: known += 1
    if known < 5: return None
    total = max(o+l for _, o, l in extents)
    if total > len(data) - j: return None
    return total

for dll_name in ("cohtml.WindowsDesktop.dll", "cohtml_icuuc.dll",
                  "RenoirCore.WindowsDesktop.dll", "crs-client.dll",
                  "crs-handler.exe", "v8.dll", "v8_libbase.dll"):
    p = os.path.join(GAME, dll_name)
    if not os.path.isfile(p): continue
    data = open(p, "rb").read()
    print(f"\n=== {dll_name} ({len(data)} bytes) ===")
    fonts = []
    for magic in (b"OTTO", b"\x00\x01\x00\x00"):
        i = 0
        while True:
            j = data.find(magic, i)
            if j < 0: break
            total = validate_otf(data, j)
            if total and 30_000 < total < 50_000_000:
                fonts.append((j, magic, total))
                outp = os.path.join(OUT, f"{dll_name}_off{j}_{magic.decode('ascii','replace').strip()}.bin")
                with open(outp, "wb") as f: f.write(data[j:j+total])
                # check Hebrew via fontTools
                try:
                    from fontTools.ttLib import TTFont
                    f = TTFont(outp, lazy=False)
                    name = f['name']
                    fam = "?"
                    for r in name.names:
                        if r.nameID == 1 and r.platformID == 3:
                            try: fam = r.toUnicode(); break
                            except: pass
                    cmap = f.getBestCmap()
                    heb = sum(1 for cp in cmap if 0x590 <= cp <= 0x5FF)
                    ara = sum(1 for cp in cmap if 0x600 <= cp <= 0x6FF)
                    print(f"  FONT [{j}] {magic!r} totalLen={total}  family={fam!r}  Hebrew={heb}  Arabic={ara}")
                    f.close()
                except Exception as ex:
                    print(f"  FONT [{j}] {magic!r} totalLen={total} (fontTools err: {ex})")
            i = j + 4
    # font-related strings inside this DLL
    for needle in (b"AzbukaPro", b"NotoSans", b"Arial Unicode", b"Arial", b"Segoe",
                   b"font-family", b"@font-face", b".ttf", b".otf",
                   b"DefaultFont", b"FallbackFont", b"DefaultFontFamily",
                   b"GenericSerif", b"GenericSansSerif", b"GenericMonospace",
                   b"hebrew", b"Hebrew", b"arabic", b"Arabic"):
        c = data.count(needle)
        if c:
            j = data.find(needle)
            start = max(0, j-40)
            end = min(len(data), j+150)
            ctx = data[start:end]
            txt = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in ctx)
            print(f"  {needle!r:<30} x{c}  [{j}]: {txt}")
