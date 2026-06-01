"""Resolve the @font-face URL paths to actual asset IDs and map them to our
4 extracted fonts."""
import os, sys, struct
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
TOC  = os.path.join(GAME, "toc")
OUT = os.path.join(ROOT, "games", "spiderman2", "extracted", "found_fonts_real")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib

with open(TOC, "rb") as f:
    toc = dat1lib.read(f)
toc.set_archives_dir(GAME)

# Identified 4 fonts:
KNOWN = {
    422626: "Arial Unicode MS Normal (23.4 MB)",
    15610:  "Arial Unicode MS Bold (17.9 MB)",
    298871: "M 盈黑 PRC W2 (Chinese, 7 MB)",
    396876: "M 盈黑 PRC W4 (Chinese, 6.8 MB)",
}

# Read the @font-face file to see exact URLs
e = next((toc.get_asset_entry_by_index(i) for i in range(len(toc.get_assets_section().ids)) if toc.get_asset_entry_by_index(i) and toc.get_asset_entry_by_index(i).index == 320895), None)
# faster: find directly
aid_section = toc.get_assets_section()
for idx in range(len(aid_section.ids)):
    ee = toc.get_asset_entry_by_index(idx)
    if ee and ee.index == 320895:
        e = ee; break

d = bytes(toc.extract_asset(e))[36:]
print("=== full @font-face CSS (idx 320895) ===")
print(d.decode("utf-8", "replace"))
print()

# Try resolving the font URLs via known path patterns
CANDIDATES = [
    "fonts/AzbukaPro.ttf",
    "fonts/AzbukaPro-Bold.ttf",
    "fonts/AzbukaPro-Medium.ttf",
    "fonts/AzbukaPro-Black.ttf",
    "fonts/MagicSpellJF.otf",
    "ui/fonts/AzbukaPro.ttf",
    "userinterface/fonts/AzbukaPro.ttf",
    "uiresources/fonts/AzbukaPro.ttf",
    "ui/uiresources/fonts/AzbukaPro.ttf",
    "userinterface/uiresources/fonts/AzbukaPro.ttf",
    "css/fonts/AzbukaPro.ttf",
    # Try with backslashes
    "fonts\\AzbukaPro.ttf",
    # With ../ prefix from CSS perspective
    "../fonts/AzbukaPro.ttf",
]

print("=== resolving font URLs via TOC ===")
for path in CANDIDATES:
    es = toc.get_asset_entries_by_path(path)
    es = [x for x in (es or []) if x is not None]
    if es:
        print(f"  [+] '{path}' -> {len(es)} entries")
        for x in es[:5]:
            label = KNOWN.get(x.index, "")
            print(f"    idx={x.index} arch={x.archive} size={x.size}  {label}")
    else:
        # silent — too noisy
        pass

# Brute-force: each of 4 known fonts has an idx. What's its PATH from TOC?
print()
print("=== for each known font, can we reverse-find its path? ===")
# We don't have a reverse map; but we can check if the CSS URL resolves to one of them
# Instead: dump some known asset entries' details and see if there's any hint
for known_idx, label in KNOWN.items():
    print(f"\n  asset idx {known_idx} = {label}")
    ee = next((toc.get_asset_entry_by_index(i) for i in range(len(aid_section.ids))
               if toc.get_asset_entry_by_index(i) and toc.get_asset_entry_by_index(i).index == known_idx), None)
    if ee:
        print(f"    asset_id={ee.asset_id}  (hex={ee.asset_id:016X})")
        print(f"    archive={ee.archive}  offset={ee.offset}  size={ee.size}")

# Also try CSS dir-based: ../../../../fonts/...
print()
print("=== trying broader URL bases ===")
PREFIXES = ["", "ui/", "ui\\", "UI/", "UI\\", "css/", "/css/",
            "ui/css/", "ui/loaded/", "ui/loaded/authored/",
            "ui/loaded/authored/art/", "ui/loaded/authored/art/fonts/",
            "ui/loaded/authored/css/", "userinterface/", "userinterface/loaded/"]
NAMES = ["AzbukaPro.ttf", "AzbukaPro-Bold.ttf", "AzbukaPro-Medium.ttf", "AzbukaPro-Black.ttf", "MagicSpellJF.otf"]
for prefix in PREFIXES:
    for name in NAMES:
        p = prefix + name
        es = toc.get_asset_entries_by_path(p)
        es = [x for x in (es or []) if x is not None]
        if es:
            print(f"  [+] '{p}' -> first idx={es[0].index} size={es[0].size}")
