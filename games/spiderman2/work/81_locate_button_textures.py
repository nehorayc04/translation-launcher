"""Locate the input-prompt button textures in the TOC by path-CRC64.
The config references ui\\textures\\buttons\\ps4\\key_1 and a sprite block with
mkb_keyboard_arrow / mouse_4 / square / triangle / circle / DpadUp ... .
Try many path variants + extensions to confirm which button-prompt textures
exist as assets, so we know the icon source is an image atlas (not a font)."""
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
    "ui/textures/buttons/ps4/", "ui/textures/buttons/ps5/", "ui/textures/buttons/pc/",
    "ui/textures/buttons/mkb/", "ui/textures/buttons/xbox/", "ui/textures/buttons/steam/",
    "ui/textures/buttons/", "textures/buttons/ps4/", "textures/buttons/",
    "ui/art/buttons/", "ui/loaded/authored/_common/textures/buttons/ps4/",
    "ui/loaded/authored/_common/textures/buttons/",
]
NAMES = [
    "key_1", "key_28", "mkb_keyboard_arrow", "mouse_4", "mouse_middle", "mouse_wheel",
    "square", "triangle", "circle", "cross", "l1", "r1", "l2", "r2",
    "DpadUp", "dpad_up", "stick_up", "_enter", "back", "menu", "view",
]
EXTS = [".png", ".dds", ".texture", "", ".basis", ".ktx"]

print("Probing button-prompt textures by path-CRC64 ...\n")
found = 0
for name in NAMES:
    for pre in PREFIXES:
        hit = None
        for ext in EXTS:
            path = pre + name + ext
            aid = crc64.hash(path)
            ents = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
            if ents:
                e = ents[0]
                hit = (path, aid, e)
                break
        if hit:
            path, aid, e = hit
            print(f"[+] {name:20s} -> {path!r}")
            print(f"      aid=0x{aid:016X} archive={e.archive}({arch_name.get(e.archive,'?')}) "
                  f"size={e.size}")
            found += 1
            break
print(f"\n[*] matched {found}/{len(NAMES)} probe names")
