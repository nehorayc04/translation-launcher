"""Enumerate the full input-prompt button-texture set. The config sprite blocks
listed names like mkb_keyboard_arrow / mouse_4 / square / triangle / l1 / DpadUp.
Probe every (platform-folder x name x ext) by path-CRC64 to map the complete
atlas. Confirms the prompt icons are textures in d\\tex_ui (not font glyphs),
and shows whether a keyboard/mouse (mkb / pc) prompt set exists."""
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

PLATFORMS = ["ps4", "ps5", "pc", "mkb", "xbox", "steam", "switch", "stadia"]
# names harvested from the config sprite blocks
NAMES = [
    "key_1","key_2","key_28","key_enter","enter",
    "mkb_keyboard_arrow","keyboard_arrow","arrow",
    "mouse","mouse_1","mouse_2","mouse_3","mouse_4","mouse_5",
    "mouse_left","mouse_right","mouse_middle","middle","mouse_wheel","wheel",
    "wheel_up","wheel_down","horizontal","vertical","scroll",
    "square","triangle","circle","cross","l1","r1","l2","r2","l3","r3",
    "lb","rb","lt","rt","dpad_up","dpad_down","dpad_left","dpad_right",
    "DpadUp","DpadDown","DpadLeft","DpadRight","dpad_swipe","swapanalog",
    "stick_up","stick_left","left_stick","right_stick",
    "back","menu","view","options","share","start","select","one","two",
    "grip","top","softpull","hold","swipe","steam",
]
EXTS = [".texture", ".png", ".dds", "", ".basis"]
ROOTS = [
    "ui/textures/buttons/{p}/{n}",
    "ui/textures/buttons/{n}",
    "ui/textures/buttons/mkb/{n}",
    "ui/textures/buttons/keyboard/{n}",
]

found = {}
for plat in PLATFORMS + [None]:
    for name in NAMES:
        for tmpl in ROOTS:
            if "{p}" in tmpl and plat is None:
                continue
            if "{p}" not in tmpl and plat is not None:
                continue
            base = tmpl.format(p=plat or "", n=name)
            for ext in EXTS:
                path = base + ext
                aid = crc64.hash(path)
                ents = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
                if ents:
                    e = ents[0]
                    found[path] = (aid, e.archive, e.size)
                    break

print(f"[*] {len(found)} button textures resolved in TOC:\n")
# group by folder
from collections import defaultdict
byfolder = defaultdict(list)
for path,(aid,arch,size) in sorted(found.items()):
    folder = path.rsplit("/",1)[0]
    byfolder[folder].append((path.rsplit("/",1)[1], aid, arch, size))
for folder in sorted(byfolder):
    arc = byfolder[folder][0][2]
    print(f"  {folder}/   (archive {arc} = {arch_name.get(arc,'?')})  [{len(byfolder[folder])} sprites]")
    for nm, aid, arch, size in byfolder[folder]:
        print(f"      {nm:24s} aid=0x{aid:016X} size={size}")
