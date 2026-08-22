"""Locate the lowercase lobby-header font assets (azbukapro_regular_normal.ttf
and azbukapromedium_regular_normal.ttf) by brute-forcing path prefixes through
path-CRC64. These are referenced by separate @font-face blocks and were never
swapped -> they draw the still-tofu lobby header."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

NAMES = ["azbukapro_regular_normal.ttf", "azbukapromedium_regular_normal.ttf",
         "azbukaprobold_regular_normal.ttf", "azbukaproblack_regular_normal.ttf"]
SCENES = ["_common", "Amon", "amon", "SlottedGadgets", "slottedgadgets",
          "frontend", "pause", "pausemenu", "lobby", "mainmenu", "menu",
          "loadgame", "startup", "boot", "common", "hud", "shared",
          "Common", "Frontend", "Pause", "Lobby", "MainMenu", "Menu"]
PREFIXES = [
    "ui/loaded/authored/{s}/fonts/", "ui/loaded/authored/{s}/Fonts/",
    "ui/loaded/authored/{s}/font/", "ui/loaded/authored/{s}/Font/",
    "ui/authored/{s}/fonts/", "ui/authored/{s}/Fonts/",
    "ui/{s}/fonts/", "ui/{s}/Fonts/",
    "ui/loaded/{s}/fonts/", "ui/loaded/{s}/Fonts/",
    "ui/loaded/authored/_common/{s}/fonts/",
    "ui/loaded/authored/_common/{s}/",
    "{s}/fonts/", "{s}/Fonts/", "fonts/", "Fonts/", "",
]

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)
archs = toc.get_archives_section()
arch_name = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii", "replace")
             for i, a in enumerate(archs.archives)}

found = {}
for name in NAMES:
    hit = None
    for s in SCENES:
        for pf in PREFIXES:
            path = pf.format(s=s) + name
            aid = crc64.hash(path)
            ents = toc.get_asset_entries_by_assetid(aid, stop_on_first=True)
            if ents:
                e = ents[0]
                hit = (path, aid, e)
                print(f"[+] {name}")
                print(f"      path     = {path!r}")
                print(f"      asset_id = 0x{aid:016X}")
                print(f"      archive  = {e.archive} ({arch_name.get(e.archive)})")
                print(f"      size     = {e.size}")
                found[name] = hit
                break
        if hit:
            break
    if not hit:
        print(f"[-] {name}: NO prefix matched (need another approach)")
    print()

# If found, dump + check coverage quickly
if found:
    import struct
    def cov(data):
        try:
            nt = struct.unpack(">H", data[4:6])[0]
            t = {}
            for k in range(nt):
                rec = data[12+k*16:12+(k+1)*16]
                t[rec[:4]] = struct.unpack(">II", rec[8:16])
            off, ln = t[b"cmap"]; c = data[off:off+ln]
            num = struct.unpack(">H", c[2:4])[0]; best=None
            for k in range(num):
                p,en,so = struct.unpack(">HHI", c[4+k*8:12+k*8])
                if (p==0) or (p==3 and en in (1,10)): best=so
            sub=c[best:]; fmt=struct.unpack(">H",sub[:2])[0]; cps=set()
            if fmt==4:
                seg=struct.unpack(">H",sub[6:8])[0]//2; eo=14; so=eo+2*seg+2
                end=struct.unpack(f">{seg}H",sub[eo:eo+2*seg]); st=struct.unpack(f">{seg}H",sub[so:so+2*seg])
                for a,b in zip(st,end):
                    if a!=0xFFFF: cps.update(range(a,min(b,0xFFFF)+1))
            heb=sum(1 for x in cps if 0x590<=x<=0x5FF); ara=sum(1 for x in cps if 0x600<=x<=0x6FF)
            return f"HEB={heb}/112 ARA={ara}/256 glyphs={len(cps)}"
        except Exception as ex:
            return f"(parse err: {ex})"
    for name,(path,aid,e) in found.items():
        raw=bytes(toc.extract_asset(e))
        print(f"  {name}: head={raw[:4].hex()} {cov(raw)}")
