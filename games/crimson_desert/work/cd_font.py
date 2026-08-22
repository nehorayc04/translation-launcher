#!/usr/bin/env python3
"""cd_font.py - inject Hebrew glyphs into Crimson Desert UI TrueType fonts.

The game's UI fonts (ui/basefont*.ttf inside package group 0012) are plain
loose glyf TTFs with NO vhea/vmtx (horizontal-only, same shape as Anno 1800's
Meta font) -> reuses games/anno1800/work/anno_font.py's `_add_hebrew` merge
helper unchanged (glyf+hmtx+cmap ADD, no CR2W/DDS-atlas wrapper needed).

Font families (from the shipped `name` table, cmap-verified 0/27 Hebrew):
  basefont_eng.ttf / creditfont.ttf / minigamefont.ttf  -> "Vollkorn Medium"
  basefont.ttf (pre-language-select default)            -> "Yoon Gokulyeo Light"
Donor: FrankRuhlLibre-Medium.ttf (already vendored in this repo for
Corsair Cove; a calligraphic humanist serif -- the same class of match as
Vollkorn, matching this project's "fantasy epic" register).

CLI:
    cd_font.py inject-all <extracted_fonts_dir> <out_dir>
    cd_font.py check <font.ttf>
"""
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "games", "anno1800", "work"))
import anno_font  # noqa: E402

DONOR = r"C:\Windows\Fonts\FrankRuhlLibre-Medium.ttf"

TARGET_FONTS = [
    "basefont.ttf",
    "basefont_eng.ttf",
    "creditfont.ttf",
    "minigamefont.ttf",
]


def inject_all(fonts_dir: str, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for fname in TARGET_FONTS:
        src_path = os.path.join(fonts_dir, fname)
        if not os.path.exists(src_path):
            print(f"[skip] {fname} not found in {fonts_dir}")
            continue
        out_path = os.path.join(out_dir, fname)
        added, skipped, used_src, subbed = anno_font.inject(src_path, out_path, DONOR)
        results[fname] = {"added": added, "skipped": skipped}
        print(f"{fname}: injected {added} Hebrew glyphs (skipped {skipped}) from {os.path.basename(used_src)}")
        anno_font.check(out_path)
        # Sanity: also confirm Latin is untouched (26/26).
    return results


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "inject-all":
        inject_all(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "check":
        anno_font.check(sys.argv[2])
    else:
        print(__doc__)
        raise SystemExit(2)
