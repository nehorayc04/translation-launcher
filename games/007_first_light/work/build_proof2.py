"""
build_proof2.py — 007 First Light Hebrew MENU-PROOF via the PROVEN append-relocate deploy
(append_reloc.py), NOT the broken patch-RPKG format.

Proves end-to-end in ONE launch: Hebrew menu strings (VISUAL/RTL) + injected Hebrew GFXF font
render in-game. One target is a pure-Latin marker (proves the deploy loads independent of font).

  gl_locr.decode/encode + gl_rtl.to_visual (VISUAL) + gl_gfxf.inject_hebrew  ->  overrides
  -> append_reloc.deploy (append each edited resource at chunk0 EOF, repoint table offsets)

Usage:  python build_proof2.py deploy     (launch game -> main menu, report)
        python build_proof2.py revert
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)

from gl_rpkg import RPKG
import gl_locr as L
import gl_rtl as RTL
import gl_gfxf as GFXF
import append_reloc as AR

CHUNK0 = AR.CHUNK0
UI_FONT_HASH = 0x01DD9580958CDC9B
HEB_TTF = r"C:\Windows\Fonts\arial.ttf"   # proof font (final atmosphere font is Phase-2)
WITH_FONT = True
FONT_ONLY = ["Arya"]   # test: Arya only (small GFXF)

MARKER = "@ZZ-007-OK-ZZ"
TARGETS = [
    (0x01C76A08493EEE11, 0xB3597EF8, "המשך"),          # Continue (hidden for new player, still patched)
    (0x01B4B8D71B46C3B8, 0x023510F0, "אפשרויות"),       # Options  -> visible on main menu
    (0x01B4B8D71B46C3B8, 0x167643D4, MARKER),           # Language -> Latin marker
    (0x01CF5B1F67C9AC83, 0xC67091A6, "המשך משחק"),      # Resume
    (0x01CF5B1F67C9AC83, 0x0C18686D, "טען משחק"),       # Load game
    (0x01CF5B1F67C9AC83, 0x34C8F39F, "קרדיטים"),        # Credits
]


def _val(repl):
    return repl[1:] if repl.startswith("@") else RTL.to_visual(repl)


def _overrides():
    base = RPKG(CHUNK0)
    by_res = {}
    for res_hash, line_hash, repl in TARGETS:
        by_res.setdefault(res_hash, {})[line_hash] = _val(repl)

    overrides = {}
    for res_hash, edit_map in by_res.items():
        ver, langs = L.decode_locr(base.read(base._by_hash[res_hash]))
        n = 0
        for block in langs:
            for j, (h, s) in enumerate(block or []):
                if h in edit_map:
                    block[j] = (h, edit_map[h]); n += 1
        overrides[res_hash] = L.encode_locr(langs, version=ver)
        print(f"  LOCR {res_hash:016X}: patched {n} entries ({len(edit_map)} keys x slots)")

    if WITH_FONT:
        new_gfxf, report = GFXF.inject_hebrew(base.read(base._by_hash[UI_FONT_HASH]), HEB_TTF,
                                              only_names=FONT_ONLY)
        overrides[UI_FONT_HASH] = new_gfxf
        print(f"  GFXF {UI_FONT_HASH:016X}: +Hebrew into {len(report)} fonts "
              f"({', '.join(n for _, n, _ in report)})")
    else:
        print("  GFXF skipped")
    return overrides


def deploy():
    AR.deploy(_overrides())
    print("Launch -> main menu. Hebrew (אפשרויות/המשך משחק) or the marker ZZ-007-OK-ZZ = the "
          "whole text+font+RTL pipeline works.")


def revert():
    AR.revert()


if __name__ == "__main__":
    {"deploy": deploy, "revert": revert}[sys.argv[1]]()
