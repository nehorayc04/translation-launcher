"""Isolation test: deploy ONLY span 8's loc (leave span 0 and span 152 fully vanilla/
untouched, and leave the font vanilla too) to determine whether the pre-game "Launcher"
screen reads span 0 (kLanguageNone) specifically -- if it does, it should show CORRECT
English even with this deploy, since span 0's archive entry never changes.

If the Launcher STILL breaks with only span 8 touched, that rules out "wrong span" and
implicates something about archive-table growth / the redirect mechanism itself, generic
to any appended archive.

Usage:
    python 32_isolate_launcher.py span8-only     # patch only span 8
    python 32_isolate_launcher.py font-only      # patch only the font, no loc at all
    python 32_isolate_launcher.py --revert
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / "games" / "spiderman_remastered" / "tools"
sys.path.insert(0, str(TOOLS))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import msmr_loc      # noqa: E402
import msmr_deploy    # noqa: E402
import msmr_font      # noqa: E402

GAME = Path(os.environ.get("MSMR_GAME", r"D:\Games\Spider-man Remastered"))
LOCS = ROOT / "games" / "spiderman_remastered" / "extract" / "loc_variants"
FONTS = ROOT / "games" / "spiderman_remastered" / "extract" / "fonts"

EN_ASSET_ID = 0xBE55D94F171BF8DE
FONT_ASSET_ID = 0xB1BC4746124FA7ED
FONT_SPAN = 0


def deploy_span8_only():
    loc = msmr_loc.load(LOCS / "variant_01_idx239528.localization")
    patch = {"TEXT_SPLASHSCREEN_CONTINUE": "ZZ-SPAN8-ISOLATE-ZZ"}
    blob = loc.encode(patch)
    print(f"[*] span 8 only -> {len(blob)} B")
    res = msmr_deploy.apply(GAME, [(8, EN_ASSET_ID, blob)])
    print("[*] deploy ->", res)
    if not res.get("ok"):
        raise SystemExit(res.get("error"))
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(GAME))
    t.set_archives_dir(str(msmr_deploy.arch_dir(GAME)))
    slot = msmr_deploy.find_asset_index(t, 8, EN_ASSET_ID)
    raw = bytes(t.extract_asset(slot))
    d = msmr_loc.Loc(raw).as_dict()
    print("[*] read-back marker:", d.get("TEXT_SPLASHSCREEN_CONTINUE"))
    print("[*] read-back LAUNCHER_PLAY:", d.get("LAUNCHER_PLAY"))
    # span 0 must be COMPLETELY untouched -- verify it's still the original archive index
    slot0 = msmr_deploy.find_asset_index(t, 0, EN_ASSET_ID)
    off0 = t.get_offsets_section().entries[slot0]
    print(f"[*] span 0 offset entry UNCHANGED check: archive_index={off0.archive_index} "
          f"(should be a LOW/original index, not one of our new mods/ entries)")
    print("\n[+] Now launch the game and check the pre-game Launcher screen:")
    print("    - shows 'Play'/'Settings'/etc CORRECTLY  -> Launcher does NOT read span 8")
    print("      (this would mean span 0 -- or something else -- feeds it, and the raw-key")
    print("       bug we saw before was from patching span 0 too)")
    print("    - STILL shows raw LAUNCHER_PLAY etc keys  -> span 8 alone breaks it, OR")
    print("      the bug is generic to ANY appended archive (archive-table growth itself)")


def deploy_font_only():
    font_bytes = (FONTS / "Font_LatinAS3_0.bin").read_bytes()
    new_font = msmr_font.inject(font_bytes)
    print(f"[*] font only -> {len(new_font)} B")
    res = msmr_deploy.apply(GAME, [(FONT_SPAN, FONT_ASSET_ID, new_font)])
    print("[*] deploy ->", res)
    if not res.get("ok"):
        raise SystemExit(res.get("error"))
    print("\n[+] Now launch the game and check the pre-game Launcher screen:")
    print("    - shows 'Play'/'Settings'/etc CORRECTLY -> font-only append is safe,")
    print("      loc redirect specifically is the trigger")
    print("    - shows raw LAUNCHER_PLAY etc keys -> archive-table growth ALONE (even with")
    print("      zero loc changes) is enough to break it -- generic bug, not loc-specific")


def revert():
    print(msmr_deploy.revert(GAME))


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "span8-only" in sys.argv:
        deploy_span8_only()
    elif "font-only" in sys.argv:
        deploy_font_only()
    else:
        print(__doc__)
