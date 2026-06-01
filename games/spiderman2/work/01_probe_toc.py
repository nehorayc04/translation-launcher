"""Probe the SM2 toc: list archives, count assets, dump first few asset IDs."""
import os, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")

sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))

import dat1lib
import dat1lib.types.toc

print("[*] toc path:", TOC, "exists:", os.path.exists(TOC), "size:", os.path.getsize(TOC))

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)

print("[*] class:", type(toc).__name__, "module:", type(toc).__module__)
print("[*] dir:", [m for m in dir(toc) if not m.startswith("_")])

if hasattr(toc, "get_archives_section"):
    archs = toc.get_archives_section()
    aids  = toc.get_assets_section()
    print("[+] archives:", len(archs.archives), "assets:", len(aids.ids))
    print()
    print("=== first 25 archives ===")
    for i, a in enumerate(archs.archives[:25]):
        print(f"  [{i:4}] {a}")
    print()
    print("=== last 5 archives ===")
    for i, a in enumerate(archs.archives[-5:], start=len(archs.archives)-5):
        print(f"  [{i:4}] {a}")
    print()
    print("=== first 5 asset IDs ===")
    for i, aid in enumerate(aids.ids[:5]):
        print(f"  [{i:4}] {aid!r}")
