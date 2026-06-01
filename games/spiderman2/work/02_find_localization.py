"""Dig deeper: archive entries' attrs, locate the 'localization' archive,
try to find localization assets by known Insomniac paths."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib, dat1lib.types.toc2

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

archs = toc.get_archives_section()
print("[*] ArchiveFileEntry attrs:", [m for m in dir(archs.archives[0]) if not m.startswith("_")])
print()
print("=== archive entries that mention 'localization' ===")
for i, a in enumerate(archs.archives):
    info = {m: getattr(a, m) for m in dir(a) if not m.startswith("_") and not callable(getattr(a, m))}
    s = " ".join(str(v) for v in info.values())
    if "localization" in s.lower():
        print(f"  [{i:4}] {info}")

print()
print("=== try resolving common localization paths via get_asset_entries_by_path ===")
candidates = [
    "localization/arabic.localization",
    "localization/english.localization",
    "localization/localization_all.localization",
    "arabic.localization",
    "english.localization",
    "localization/arabic",
    "d/localization/arabic.localization",
]
for p in candidates:
    try:
        entries = toc.get_asset_entries_by_path(p)
        print(f"  '{p}' -> {len(entries) if entries else 0} entries")
        if entries:
            for e in entries[:3]:
                print("     ", {m: getattr(e, m) for m in dir(e) if not m.startswith("_") and not callable(getattr(e, m))})
    except Exception as ex:
        print(f"  '{p}' -> ERROR: {ex}")

# also: dump an asset header to learn what fields are available, in case there
# is an asset-name table somewhere
hdrs = toc.get_asset_headers_section()
print()
print("[*] asset headers section attrs:", [m for m in dir(hdrs) if not m.startswith("_") and not callable(getattr(hdrs, m, None))])
if hasattr(hdrs, "entries") and hdrs.entries:
    print("[*] first header entry attrs:", [m for m in dir(hdrs.entries[0]) if not m.startswith("_")])
    print("[*] first 3:", [vars(e) for e in hdrs.entries[:3]])
