"""Locate the Arabic font asset (NeueFrutigerArabic) in the TOC by path-CRC64,
plus the AzbukaPro faces. Report archive / offset / size / asset_id and dump
the raw asset so we can reconstruct + verify coverage."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT  = os.path.join(ROOT, "games", "spiderman2", "extracted", "fontmap_assets")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

PREFIXES = [
    "ui/loaded/authored/_common/fonts/",
    "ui/loaded/authored/_common/font/",
    "ui/loaded/authored/_common/",
    "loaded/authored/_common/fonts/",
    "authored/_common/fonts/",
    "_common/fonts/",
    "fonts/",
    "",
]
NAMES = [
    "NeueFrutigerArabic-Regular.ttf",
    "AzbukaPro-Regular.ttf",
    "AzbukaPro-Medium.ttf",
    "AzbukaPro-Bold.ttf",
    "AzbukaPro-Black.ttf",
    "MagicSpellJF.otf",
]

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

# Build archive-index -> name map
archs = toc.get_archives_section()
arch_name = {}
for i, a in enumerate(archs.archives):
    nm = bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace")
    arch_name[i] = nm

print("Trying %d prefixes x %d names ...\n" % (len(PREFIXES), len(NAMES)))
found = {}
for name in NAMES:
    hit = None
    for pre in PREFIXES:
        path = pre + name
        aid = crc64.hash(path)
        entries = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
        if entries:
            e = entries[0]
            hit = (path, aid, e)
            an = arch_name.get(e.archive, "?")
            print(f"[+] {name}")
            print(f"      path     = {path!r}")
            print(f"      asset_id = 0x{aid:016X}")
            print(f"      archive  = {e.archive} ({an})")
            print(f"      offset   = {e.offset}")
            print(f"      size     = {e.size}")
            found[name] = hit
            break
    if not hit:
        print(f"[-] {name}: no path variant matched")
    print()

# Dump the raw bytes of each located font for follow-up reconstruction
for name, (path, aid, e) in found.items():
    try:
        raw = bytes(toc.extract_asset(e))
    except Exception as ex:
        print(f"  !! extract failed for {name}: {ex}")
        continue
    outp = os.path.join(OUT, name + ".rawasset")
    with open(outp, "wb") as wf:
        wf.write(raw)
    print(f"  saved {name}: {len(raw)} bytes -> {os.path.basename(outp)}  head={raw[:16].hex()}")
