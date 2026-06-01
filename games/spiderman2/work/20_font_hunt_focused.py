"""Focused font hunt — three vectors:
  A. Scan ONLY the small archives (conduit, config, localization) for TTF/OTF
  B. Search dagstr for paths containing common font/UI tokens we haven't tried
  C. Scan cohtml DLLs for hardcoded font references
"""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

# ---- A: scan small archives for TTF/OTF ----
SMALL_ARCHIVES = ["conduit", "config", "localization"]
TTF_MAGICS = [(b"\x00\x01\x00\x00", "TTF"), (b"OTTO", "OTF-CFF"), (b"ttcf", "TTC")]

for arch in SMALL_ARCHIVES:
    path = os.path.join(GAME, "d", arch)
    if not os.path.isfile(path):
        continue
    size = os.path.getsize(path)
    print(f"\n=== A: scanning d/{arch} ({size:>12} bytes) for font signatures ===")
    data = open(path, "rb").read()
    for magic, kind in TTF_MAGICS:
        idxs = []
        i = 0
        while True:
            j = data.find(magic, i)
            if j < 0: break
            # Validate TTF: numTables in range
            if magic == b"\x00\x01\x00\x00" and j + 12 < len(data):
                num_tables = struct.unpack(">H", data[j+4:j+6])[0]
                if not (4 <= num_tables <= 40):
                    i = j + 1
                    continue
                # check first table tag is ASCII
                tag = data[j+12:j+16]
                if not (len(tag) == 4 and all(0x20 <= b <= 0x7E for b in tag)):
                    i = j + 1
                    continue
            idxs.append(j)
            i = j + 4
            if len(idxs) > 30: break
        if idxs:
            print(f"  {kind} hits: {len(idxs)} at offsets {idxs[:10]}")

# ---- B: dagstr scan — broader font-related tokens ----
print()
print("=== B: dagstr font-token sweep ===")
DAGSTR = os.path.join(GAME, "dagstr")
data = open(DAGSTR, "rb").read()
SECONDARY_TOKENS = [
    b".typeface", b".bff", b".fnt", b".bmfont", b".glyph",
    b"typeface", b"bmfont",
    b"cohtml", b"CoUI", b"Coherent",
    b"main_menu_lobby", b"lobby",
    b"Heebo", b"heebo",
    b"AlegreyaSans", b"alegreya",
    b"Roboto",
    b"Inter",
    b"NotoSans", b"noto_sans",
    b"freetype",
    b"NarwoodLOC",
    # paths Insomniac uses in MSMR (per modding wikis)
    b"ui_arabic", b"ui_hebrew", b"ui_japanese",
    b"common\\font", b"common/font",
    b"\\fonts\\", b"/fonts/",
    b"ui\\fonts", b"ui/fonts",
    b"NSI", b"_loc_",
]
for t in SECONDARY_TOKENS:
    c = data.count(t)
    if c:
        print(f"  {t!r:<30} count={c}")
        i = 0; shown = 0
        while shown < 4:
            j = data.find(t, i)
            if j < 0: break
            start = j
            while start > 0 and data[start-1] != 0:
                start -= 1
            end = data.find(b"\x00", j)
            if end < 0: end = j + 200
            s = data[start:end].decode("utf-8", "replace")
            if 0 < len(s) < 200:
                print(f"    [{j:>9}] {s!r}")
                shown += 1
            i = end + 1

# ---- C: cohtml DLL inspection ----
print()
for dll in ("cohtml.WindowsDesktop.dll", "cohtml_icuuc.dll",
            "RenoirCore.WindowsDesktop.dll"):
    p = os.path.join(GAME, dll)
    if not os.path.isfile(p): continue
    print(f"\n=== C: scanning {dll} ({os.path.getsize(p):>10} bytes) ===")
    d = open(p, "rb").read()
    for t in (b".ttf", b".otf", b"NotoSans", b"Arabic.ttf", b"FontFamily",
              b"font_face", b"FontFace", b"@font-face", b"font-family",
              b"coui://", b"cohtml://", b"FontSet", b"RegisterFont"):
        c = d.count(t)
        if c:
            j = d.find(t)
            start = max(0, j-30)
            end = min(len(d), j+120)
            chunk = d[start:end]
            txt = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in chunk)
            print(f"  {t!r:<22} count={c:>4}   sample: {txt}")
