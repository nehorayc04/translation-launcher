"""Brute search for the actual path of each font + the CSS file.
Approach: combine a list of common UI directory prefixes with the font filenames,
plus also try CRC64-hashed path strings in dagstr."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib, dat1lib.crc64

with open(os.path.join(GAME, "toc"), "rb") as f:
    toc = dat1lib.read(f)

# Target asset IDs
TARGET = {
    13745093436627831582: "Arial Unicode MS Normal (23.4 MB)",
    9390743670350618331: "Arial Unicode MS Bold (17.9 MB)",
    12422161487805800155: "M 盈黑 PRC W2 (Chinese)",
    13468442481688733963: "M 盈黑 PRC W4 (Chinese)",
}

_TABLE = dat1lib.crc64.table
def _crc64_step(data: bytes, crc: int) -> int:
    for b in data:
        crc = 0xFFFFFFFFFFFFFFFF & ((crc >> 8) ^ _TABLE[0xFF & (crc ^ b)])
    return crc
def crc64(s: str) -> int:
    # Insomniac normalises paths: lowercase + forward slashes
    norm = s.lower().replace("\\", "/").encode("utf-8")
    v = 0xC96C5795D7870F42
    v = _crc64_step(norm, v)
    return (v >> 2) | 0x8000000000000000

# Common Insomniac UI paths
DIRS = [
    "ui/", "userinterface/", "uiresources/",
    "ui/loaded/", "ui/loaded/authored/", "ui/loaded/authored/art/",
    "ui/loaded/authored/Art/", "userinterface/loaded/",
    "coh/", "cohtml/", "css/", "fonts/", "Fonts/",
    "ui/css/", "ui/css/fonts/", "ui/fonts/",
    "ui/loaded/authored/css/", "ui/loaded/authored/css/fonts/",
    "ui/loaded/authored/art/fonts/",
    "Ui/Css/Fonts/", "UI/CSS/Fonts/",
    "userinterface/css/fonts/", "userinterface/fonts/",
    "uiresources/css/fonts/", "uiresources/fonts/",
    "ui/loaded/authored/art/css/fonts/",
    "ui/loaded/authored/coh/",
    "ui/loaded/authored/coh/fonts/",
    "ui/uiresources/", "ui/uiresources/fonts/",
    "loaded/authored/", "loaded/authored/art/fonts/",
    "loaded/", "loaded/uiresources/", "loaded/uiresources/fonts/",
    "data/", "data/ui/", "data/ui/fonts/",
    "",     # bare filename
]
NAMES = [
    "AzbukaPro.ttf", "AzbukaPro-Bold.ttf", "AzbukaPro-Medium.ttf",
    "AzbukaPro-Black.ttf", "AzbukaPro-Regular.ttf",
    "azbukapro.ttf", "azbukapro_regular.ttf",
    "MagicSpellJF.otf", "magicspelljf.otf",
    "arialuni.ttf", "ArialUni.ttf", "ARIALUNI.ttf",
    "ArialUnicodeMS.ttf", "arial_unicode_ms.ttf", "arialunicode.ttf",
    "MYingHeiPRC.ttf", "myingheiprc.ttf",
]
SEPS = ["/", "\\"]   # different separator variants

def all_paths():
    for dir_pref in DIRS:
        for name in NAMES:
            for sep in SEPS:
                # Replace any / with sep
                p = (dir_pref + name).replace("/", sep)
                yield p

print(f"[*] brute-forcing {len(DIRS)*len(NAMES)*len(SEPS)} candidate paths against TOC...")
hits = []
for p in all_paths():
    h = crc64(p)
    if h in TARGET:
        hits.append((p, h, TARGET[h]))

if hits:
    print(f"\n=== HITS ===")
    for p, h, name in hits:
        print(f"  '{p}'  -> {name}  (id={h:016X})")
else:
    print("\n  no path hits — trying via TOC's get_asset_entries_by_path instead")

# Cross-check: ask TOC directly via get_asset_entries_by_path
print()
print("=== via TOC.get_asset_entries_by_path ===")
ENT = toc.get_asset_entries_by_path
for p in all_paths():
    es = ENT(p)
    es = [e for e in (es or []) if e is not None]
    if es:
        for e in es:
            if e.index in {422626, 15610, 298871, 396876}:
                print(f"  [+] '{p}' -> font idx={e.index}  arch={e.archive}")
