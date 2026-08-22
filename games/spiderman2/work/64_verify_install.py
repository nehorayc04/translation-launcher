"""Verify the v5 (6-font) mod is actually installed: compare each font asset's
archive/offset in the live `toc` vs the pristine `toc.BAK`. If installed, the
asset now lives in a high-index mod archive, not 185 (userinterface)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
import dat1lib
from dat1lib import crc64

PATHS = {
    "AzbukaPro.ttf":        "ui/loaded/authored/_common/fonts/AzbukaPro.ttf",
    "AzbukaPro-Medium.ttf": "ui/loaded/authored/_common/fonts/AzbukaPro-Medium.ttf",
    "AzbukaPro-Bold.ttf":   "ui/loaded/authored/_common/fonts/AzbukaPro-Bold.ttf",
    "AzbukaPro-Black.ttf":  "ui/loaded/authored/_common/fonts/AzbukaPro-Black.ttf",
    "NeueFrutigerArabic":   "ui/loaded/authored/_common/fonts/NeueFrutigerArabic-Regular.ttf",
    "MagicSpellJF.otf":     "ui/loaded/authored/_common/fonts/MagicSpellJF.otf",
}

def load(tocfile):
    with open(os.path.join(GAME, tocfile), "rb") as f:
        t = dat1lib.read(f)
    t.set_archives_dir(GAME)
    archs = {i: bytes(a.filename).split(b"\x00")[0].decode("ascii","replace")
             for i,a in enumerate(t.get_archives_section().archives)}
    return t, archs

live, live_arch = load("toc")
try:
    bak, bak_arch = load("toc.BAK")
except Exception:
    bak, bak_arch = None, {}

print(f"{'font':<22}{'BAK arch':<26}{'LIVE arch':<26}{'changed?'}")
for name, path in PATHS.items():
    aid = crc64.hash(path)
    le = live.get_asset_entries_by_assetid(aid, stop_on_first=True)
    be = bak.get_asset_entries_by_assetid(aid, stop_on_first=True) if bak else []
    ls = f"{le[0].archive} ({live_arch.get(le[0].archive)}) sz={le[0].size}" if le else "MISSING"
    bs = f"{be[0].archive} ({bak_arch.get(be[0].archive)}) sz={be[0].size}" if be else "MISSING"
    changed = ""
    if le and be:
        changed = "YES (modded)" if (le[0].archive != be[0].archive or le[0].size != be[0].size) else "no (original)"
    print(f"{name:<22}{bs:<26}{ls:<26}{changed}")

print("\nArchives referenced by toc (high indices = injected mod archives):")
for i in sorted(live_arch):
    if i >= 185:
        print(f"  [{i}] {live_arch[i]}")
