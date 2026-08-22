"""Locate the accessibility / system feature-icon textures (the radial per-option
symbols, e.g. slow-mo) in the TOC. The AccessibilityIconToggleSettings config
points icons at ui\\...\\art\\textures\\system\\... . Probe likely texture paths."""
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
archs = toc.get_archives_section().archives
arch_name = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii","replace")
             for i, a in enumerate(archs)}

PREFIXES = [
    "ui/textures/system/", "ui/textures/hud/", "ui/textures/accessibility/",
    "ui/textures/menu/", "ui/textures/icons/", "ui/textures/settings/",
    "ui/textures/buttons/mkb/", "ui/textures/buttons/pc/", "ui/textures/buttons/keyboard/",
    "ui/loaded/authored/art/textures/system/",
]
NAMES = [
    "slomo", "slow_mo", "slowmo", "gameplay_speed", "time_dilation",
    "accessibility", "hold", "mouse", "keyboard", "mkb_keyboard_arrow",
    "mouse_left", "mouse_right", "key", "feature", "speed",
]
EXTS = [".texture", ".png", ".dds", ""]

found = {}
for pre in PREFIXES:
    for name in NAMES:
        for ext in EXTS:
            path = pre + name + ext
            aid = crc64.hash(path)
            ents = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
            if ents:
                e = ents[0]
                found[path] = (aid, e.archive, e.size)
                break

print(f"[*] {len(found)} accessibility/system icon textures resolved:\n")
for path, (aid, arch, size) in sorted(found.items()):
    print(f"  {path:55s} aid=0x{aid:016X} arch={arch}({arch_name.get(arch,'?')}) size={size}")
