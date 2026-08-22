"""Fast path-CRC64 search: load ALL asset ids into a set once, then test
thousands of candidate font paths by O(1) membership. Find where the
lowercase lobby fonts live."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
ids = toc.get_assets_section().ids
id_to_index = {}
for i, a in enumerate(ids):
    id_to_index.setdefault(a, i)
id_set = id_to_index.keys()
print(f"[*] {len(ids):,} asset ids loaded")
arch_name = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii","replace")
             for i,a in enumerate(toc.get_archives_section().archives)}

NAMES = ["azbukapro_regular_normal.ttf", "azbukapromedium_regular_normal.ttf",
         "azbukaprobold_regular_normal.ttf", "azbukaproblack_regular_normal.ttf",
         "azbukapro_bold_normal.ttf", "azbukapromedium_bold_normal.ttf"]

# Big candidate space
PKGS = ["", "_common", "Amon", "amon", "AmonRa", "SlottedGadgets",
        "Overlay", "HUD", "hud", "Frontend", "frontend", "Pause", "pause",
        "PauseMenu", "pausemenu", "Lobby", "lobby", "MainMenu", "mainmenu",
        "Menu", "menu", "Common", "common", "Shared", "shared", "FrontEnd",
        "Boot", "boot", "Loading", "loading", "Gadgets", "gadgets"]
ROOTS = ["ui/loaded/authored/", "ui/authored/", "ui/loaded/", "ui/", ""]
FDIRS = ["fonts/", "Fonts/", "font/", "Font/", "FONTS/", ""]

found = []
tested = 0
for name in NAMES:
    for r in ROOTS:
        for pkg in PKGS:
            for fd in FDIRS:
                p = f"{r}{pkg}/{fd}{name}" if pkg else f"{r}{fd}{name}"
                p = p.replace("//", "/")
                tested += 1
                aid = crc64.hash(p)
                if aid in id_to_index:
                    idx = id_to_index[aid]
                    e = toc.get_asset_entry_by_index(idx)
                    found.append((p, aid, e))
                    print(f"[+] {p!r}")
                    print(f"      asset_id=0x{aid:016X} archive={e.archive} "
                          f"({arch_name.get(e.archive)}) size={e.size}")
print(f"\n[*] tested {tested} paths, found {len(found)}")
