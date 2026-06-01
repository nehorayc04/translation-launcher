"""Aggressive font hunt:
  1. raw byte-scan of dagstr+dag for ANY font-y substring
  2. inspect AssetHeaders section to find type tags relating to fonts
  3. peek at d/conduit's magic (small archive — might house UI fonts)
  4. try paths that match what Insomniac engines (Sunset Overdrive / MSMR) used."""
import os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

# Part 1: byte scan dagstr+dag for likely font tokens
TOKENS = [b"font", b"Font", b"FONT", b"glyph", b"Glyph", b"GLYPH",
          b"typeface", b"Typeface", b"TypeFace", b"TYPEFACE",
          b".ttf", b".otf", b".woff", b".bff",
          b"noto", b"Noto", b"NotoSans", b"Adobe", b"Roboto",
          b"freetype", b"FreeType",
          b"cohtml", b"CoHTML", b"CoUI", b"Coherent"]

for fn in ("dagstr", "dag"):
    print(f"\n=== scanning {fn} ===")
    data = open(os.path.join(GAME, fn), "rb").read()
    for needle in TOKENS:
        count = data.count(needle)
        if count:
            print(f"  {needle!r:<30}  count={count}")
            # show a few contexts
            i = 0
            shown = 0
            while shown < 3:
                j = data.find(needle, i)
                if j < 0: break
                # walk back to start of NUL-separated string
                start = j
                while start > 0 and data[start-1] not in (0, 0xA, 0xD):
                    start -= 1
                end = data.find(b"\x00", j)
                if end < 0: end = j+200
                s = data[start:end]
                if len(s) < 200 and len(s) > 0:
                    try:
                        ss = s.decode("utf-8", "replace")
                        print(f"     [{j:>8}]  {ss!r}")
                        shown += 1
                    except: pass
                i = end + 1

# Part 2: inspect AssetHeaders to look for type tags
print()
print("=== AssetHeadersSection samples ===")
hdrs = toc.get_asset_headers_section()
print(f"  headers attr: {[a for a in dir(hdrs) if not a.startswith('_')]}")
print(f"  headers.headers type: {type(getattr(hdrs,'headers',None))}")
hh = getattr(hdrs, 'headers', None)
if hh is not None:
    print(f"  headers count: {len(hh) if hasattr(hh,'__len__') else '?'}")
    # show a few
    for i, h in enumerate(hh[:3] if hasattr(hh,'__getitem__') else []):
        print(f"   [{i}] {vars(h) if hasattr(h,'__dict__') else h}")

# Part 3: peek d/conduit
print()
print("=== d/conduit head ===")
with open(os.path.join(GAME, "d", "conduit"), "rb") as f:
    head = f.read(64)
print("  hex:", head.hex(' '))
print("  ascii:", head[:32].decode("ascii", "replace"))
# DSAR header
if head[:4] == b"DSAR":
    print("  -> DSAR archive (compressed)")

# Part 4: search for noto / fontstone / common asset registrations
print()
print("=== known Insomniac engine paths to probe ===")
PROBES = [
    "boot/boot.config", "boot/boot",
    "ui/conduit/main.conduit",
    "conduit/menu_lobby.conduit",
    "conduit/global.conduit",
    "ui/cohtml/menu_lobby.html",
    "ui/cohtml/global.css",
    "ui/cohtml/global/global.html",
    "cohtml/menu_lobby/menu_lobby.html",
    "cohtml/menu_lobby/menu_lobby.cohtml",
    # font names from MSMR via existing translations:
    "ui/fonts/freesans.bff", "ui/fonts/global.font", "ui/fonts/arabic.font",
    "fonts/noto_sans_arabic_ui.ttf",
    "fonts/sourcesanspro_regular.ttf",
    "fonts/notosansarabic-regular.ttf",
]
for p in PROBES:
    es = toc.get_asset_entries_by_path(p)
    es = [e for e in (es or []) if e is not None]
    if es:
        print(f"  [+] '{p}' -> {len(es)} entries  first: idx={es[0].index} arch={es[0].archive} size={es[0].size}")
