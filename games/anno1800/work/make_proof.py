#!/usr/bin/env python3
"""
make_proof.py - build the Anno 1800 Hebrew PROOF mod (Phase-1 gate test).

This is NOT a translation. It writes a few *diagnostic marker* Hebrew strings
onto visible main-menu GUIDs + ships Hebrew-injected UI fonts, as a loose-file
mod, so the user can launch ONCE and settle the two open gates:

  1. Does the loose mod load?           -> the menu labels change at all
  2. Does font injection work?          -> Hebrew shows as letters, not tofu boxes
  3. Native-HUD bidi mode?              -> "ימין שמאל" reads R->L (correct) or
                                           reversed "למאש ןימי" (engine non-bidi
                                           -> we must store VISUAL/pre-reversed)
  4. Digit handling on mixed lines      -> "12 עברית 34" places numbers correctly
  5. CEF stat panels                    -> (separate, checked in the stats overlay)

Build:  python work/make_proof.py
Output: Documents/Anno 1800/mods/zzz_hebrew_proof/
Remove: delete that folder.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rda_reader import RDAArchive          # noqa: E402
import anno_font                            # noqa: E402
from build_mod import visual_line          # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = r"C:/Program Files (x86)/Steam/steamapps/common/Anno 1800"
DATA4 = GAME + "/maindata/data4.rda"
MODS = os.path.join(os.path.expanduser("~"), "Documents", "Anno 1800", "mods")
MOD_NAME = "zzz_hebrew_proof"

# Inject Hebrew into every Latin UI font (the exact HUD-font binding is unconfirmed,
# so cover them all). FontAwesome/CJK are skipped.
FONT_NAMES = [
    "metaoffcpro-norm.ttf", "metaserifoffcpro-medium.ttf",
    "kelvinch.ttf", "kelvinch-bold.ttf", "kelvinch-italic.ttf", "kelvinch-bolditalic.ttf",
    "heuristica-regular.ttf", "roboto-regular.ttf", "roboto-light.ttf",
]

# A/B on slots CONFIRMED to override (154000 New Game, 154002 Options, 10438 Credits).
# Same readable phrase stored two ways -> the user tells us which reads correctly,
# resolving LOGICAL vs VISUAL for the whole 28k run.
_P = "ברוכים הבאים"
PROOF = {
    "154000": visual_line(_P),     # New Game = VISUAL (pre-reversed)
    "154002": _P,                  # Options  = LOGICAL (control, expected reversed)
    "10438":  visual_line("שלום לכולם 7"),  # Credits = VISUAL + number test
}


def build_fonts(out_fonts_dir):
    os.makedirs(out_fonts_dir, exist_ok=True)
    tmp = os.path.join(HERE, "_fonts_src")
    os.makedirs(tmp, exist_ok=True)
    # extract the needed TTFs once
    have = {f for f in os.listdir(tmp)} if os.path.isdir(tmp) else set()
    if not all(n in have for n in FONT_NAMES):
        with RDAArchive(DATA4) as a:
            for e in a.iter_entries():
                base = e.name.rsplit("/", 1)[-1]
                if e.name.startswith("data/fonts/") and base in FONT_NAMES:
                    with open(os.path.join(tmp, base), "wb") as fo:
                        fo.write(a.extract_entry(e))
    for n in FONT_NAMES:
        src = os.path.join(tmp, n)
        if not os.path.exists(src):
            print(f"  ! missing {n}, skipped")
            continue
        out = os.path.join(out_fonts_dir, n)
        added, skipped, used = anno_font.inject(src, out)
        print(f"  {n:30} +{added} Hebrew glyphs  ({os.path.basename(used)})")


def build_texts():
    # ModOps patch: adding a <Text> for an existing base GUID overrides it.
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<ModOps>"]
    for guid, heb in PROOF.items():
        lines.append(f'  <ModOp Type="add" Path="/TextExport/Texts">')
        lines.append(f"    <Text><GUID>{guid}</GUID><Text>{heb}</Text></Text>")
        lines.append(f"  </ModOp>")
    lines.append("</ModOps>")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def main():
    root = os.path.join(MODS, MOD_NAME)
    os.makedirs(os.path.join(root, "data", "config", "gui"), exist_ok=True)
    print(f"building proof mod -> {root}")

    print("injecting Hebrew into UI fonts:")
    build_fonts(os.path.join(root, "data", "fonts"))

    with open(os.path.join(root, "data", "config", "gui", "texts_english.xml"), "wb") as f:
        f.write(build_texts())
    print(f"wrote texts override ({len(PROOF)} marker GUIDs)")

    modinfo = {
        "Version": "0.0.1",
        "ModID": "nehoray_hebrew_proof",
        "Category": {"English": "Localization", "Hebrew": "תרגום"},
        "ModName": {"English": "Hebrew Proof (diagnostic)", "Hebrew": "בדיקת עברית"},
        "Description": {"English": "Phase-1 RTL/font proof. Diagnostic markers, not a translation. Set UI Language = English.",
                        "Hebrew": "בדיקת רינדור עברית RTL + פונט. סמני אבחון, לא תרגום. הגדר שפת ממשק = English."},
        "CreatorName": "Hebrew Translation Hub",
    }
    with open(os.path.join(root, "modinfo.json"), "w", encoding="utf-8") as f:
        json.dump(modinfo, f, ensure_ascii=False, indent=2)
    print("wrote modinfo.json")
    print("\nDONE. In-game: set Settings -> Language = English, restart, look at the main menu.")
    print("Report what the New Game / Options / Credits / Continue / Quit labels show.")


if __name__ == "__main__":
    main()
