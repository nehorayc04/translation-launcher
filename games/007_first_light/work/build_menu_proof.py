"""
build_menu_proof.py — assemble + deploy a 007 First Light Hebrew MENU-PROOF patch.

Proves end-to-end in ONE launch: patch-RPKG mounts + overrides the base, the Hebrew font
renders, and RTL is correct. Patches a few main-menu strings in ALL language slots (so the
proof shows Hebrew regardless of the game's language setting) — one string is a pure-Latin
marker (proves the repack loads even if the font/RTL were wrong).

Chain (all pure-Python, offline-validated tools):
  gl_locr.decode/encode (byte-identical) + gl_rtl.to_visual (VISUAL) + gl_gfxf.inject_hebrew
  (DefineFont3 +Hebrew) -> gl_rpkg_write.build_patch (chunk0patch1.rpkg) -> gl_pkgdef bump
  patchlevel + re-encrypt packagedefinition -> deploy into the game Runtime folder.

Usage:
  python build_menu_proof.py            # build only (to C:/tmp)
  python build_menu_proof.py --deploy   # build + deploy into the game (backs up first)
  python build_menu_proof.py --revert   # remove the patch + restore packagedefinition
"""
import os
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, TOOLS)

from gl_rpkg import RPKG
import gl_locr as L
import gl_rtl as RTL
import gl_gfxf as GFXF
import gl_rpkg_write as W
import gl_pkgdef as PKG

GAME = r"F:\Game Lab\007 First Light"
RUNTIME = os.path.join(GAME, "Runtime")
CHUNK0 = os.path.join(RUNTIME, "chunk0.rpkg")
PKGDEF = os.path.join(RUNTIME, "packagedefinition.txt")
PATCH_NAME = "chunk0patch1.rpkg"
UI_FONT_HASH = 0x01DD9580958CDC9B          # the Rajdhani UI GFXF
HEB_TTF = r"C:\Windows\Fonts\arial.ttf"     # proof font (final atmosphere font is Phase-2)
OUT_PATCH = "C:/tmp/" + PATCH_NAME
OUT_PKGDEF = "C:/tmp/packagedefinition.patchlevel1.txt"

# (LOCR resource hash, lineHash, replacement).  A leading "@" => pure-Latin marker (not RTL'd).
MARKER = "@ZZ-007-OK-ZZ"
TARGETS = [
    (0x01C76A08493EEE11, 0xB3597EF8, "המשך"),          # Continue
    (0x01CF5B1F67C9AC83, 0xC67091A6, "המשך משחק"),      # Resume
    (0x01CF5B1F67C9AC83, 0x0C18686D, "טען משחק"),       # Load game
    (0x01CF5B1F67C9AC83, 0x34C8F39F, "קרדיטים"),        # Credits
    (0x01B4B8D71B46C3B8, 0x023510F0, "אפשרויות"),       # Options
    (0x01B4B8D71B46C3B8, 0x167643D4, MARKER),           # Language -> Latin marker
]


def _patched_value(repl):
    if repl.startswith("@"):
        return repl[1:]                     # Latin marker, verbatim
    return RTL.to_visual(repl)              # Hebrew -> VISUAL


def build():
    base = RPKG(CHUNK0)
    # group targets by LOCR resource hash
    by_res = {}
    for res_hash, line_hash, repl in TARGETS:
        by_res.setdefault(res_hash, []).append((line_hash, _patched_value(repl)))

    overrides = {}
    # 1. patch the menu LOCRs (all language slots)
    for res_hash, edits in by_res.items():
        idx = base._by_hash[res_hash]
        ver, langs = L.decode_locr(base.read(idx))
        edit_map = dict(edits)
        n = 0
        for block in langs:
            if not block:
                continue
            for j, (h, s) in enumerate(block):
                if h in edit_map:
                    block[j] = (h, edit_map[h])
                    n += 1
        overrides[res_hash] = L.encode_locr(langs, version=ver)
        print(f"  LOCR {res_hash:016X}: patched {n} entries across slots "
              f"({len(edits)} keys x langs)")

    # 2. inject Hebrew into the UI font GFXF
    fidx = base._by_hash[UI_FONT_HASH]
    new_gfxf, report = GFXF.inject_hebrew(base.read(fidx), HEB_TTF)
    overrides[UI_FONT_HASH] = new_gfxf
    print(f"  GFXF {UI_FONT_HASH:016X}: +Hebrew into {len(report)} DefineFont3 fonts "
          f"({os.path.basename(HEB_TTF)})")

    # 3. build the patch RPKG
    W.build_patch(base, overrides, OUT_PATCH)
    print(f"  built {OUT_PATCH} ({os.path.getsize(OUT_PATCH)} bytes, {len(overrides)} resources)")

    # 4. bump packagedefinition patchlevel + re-encrypt (preserve the file's real 16-byte header)
    plain, _, hdr = PKG.decrypt(PKGDEF)
    enc = PKG.encrypt(PKG.set_patchlevel(plain, 1), hdr)
    open(OUT_PKGDEF, "wb").write(enc)
    print(f"  built {OUT_PKGDEF} (patchlevel -> 1)")
    return OUT_PATCH, OUT_PKGDEF


def deploy():
    build()
    # back up packagedefinition once
    bak = PKGDEF + ".he_backup"
    if not os.path.exists(bak):
        shutil.copy2(PKGDEF, bak)
        print(f"  backed up packagedefinition -> {bak}")
    shutil.copy2(OUT_PATCH, os.path.join(RUNTIME, PATCH_NAME))
    shutil.copy2(OUT_PKGDEF, PKGDEF)
    print(f"DEPLOYED: {PATCH_NAME} + patchlevel-1 packagedefinition into {RUNTIME}")
    print("Launch the game -> main menu. If any language shows Hebrew (המשך / אפשרויות) or the "
          "marker ZZ-007-OK-ZZ, the whole chain works.")


def revert():
    p = os.path.join(RUNTIME, PATCH_NAME)
    if os.path.exists(p):
        os.remove(p); print(f"  removed {p}")
    bak = PKGDEF + ".he_backup"
    if os.path.exists(bak):
        shutil.copy2(bak, PKGDEF); print(f"  restored packagedefinition from {bak}")
    print("REVERTED.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        revert()
    elif a.deploy:
        deploy()
    else:
        build()
        print("\n(build only — pass --deploy to install into the game)")
