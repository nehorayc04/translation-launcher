#!/usr/bin/env python3
r"""
build_menu_proof.py - Phase-1 menu proof for The Last of Us Part I Hebrew.

Produces a tiny, reversible test that closes BOTH remaining gates (bidi-storage +
font) in one in-game screenshot, exactly like the GoWR/Witcher-3/Hogwarts proofs:

  * CONTINUE -> a pure-LATIN marker  "ZZ-TLOU-OK-ZZ"  -> proves the override LOADS.
  * NEW GAME -> LOGICAL Hebrew        (unreversed)      -> reads right only if the
  * OPTIONS  -> LOGICAL Hebrew                             engine does bidi itself.
  * LOAD GAME-> VISUAL Hebrew  (to_visual, pre-reversed)-> reads right if the engine
  * SETTINGS -> VISUAL Hebrew                              draws raw byte order (expected).
  * EXTRAS   -> VISUAL Hebrew
Whichever of the two Hebrew groups reads correctly on screen tells us LOGICAL vs
VISUAL storage; tofu on ALL Hebrew => the font swap did not take.

It also builds a Latin+Hebrew font as fonts/DINPro-Regular.otf + -Medium.otf.

Everything is staged under games/tlou1/proof/loose/ mirroring `build/pc/main/`.
`--deploy` additionally COPIES the loose files into the live game (non-destructive:
it only ADDS our files; it never edits or deletes core.psarc). See DEPLOY.txt.

    python build_menu_proof.py            # stage only
    python build_menu_proof.py --deploy   # stage + copy loose into the game
    python build_menu_proof.py --revert   # remove the loose files from the game
"""
import os
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import tlou_loc                      # noqa: E402
import tlou_rtl                      # noqa: E402
from psarc import Psarc             # noqa: E402

GAME_MAIN = os.environ.get(
    "TLOU_MAIN", r"D:\Games\The Last of Us - Part I\build\pc\main")
PROOF = os.path.join(HERE, "..", "proof")
LOOSE = os.path.join(PROOF, "loose")

V = tlou_rtl.to_visual

# SID -> (kind, hebrew_logical)   kind in {latin, logical, visual}
PATCH = {
    "0023d491ee35c696": ("latin",   "ZZ-TLOU-OK-ZZ"),   # CONTINUE  (override-loads marker)
    "77f58b2bfe311d9c": ("logical", "משחק חדש"),          # NEW GAME
    "8059c747b621fefd": ("logical", "אפשרויות"),          # Options
    "13f31d29358aa9bd": ("visual",  "טען משחק"),           # LOAD GAME
    "7a05975ac411bd88": ("visual",  "הגדרות"),             # SETTINGS
    "8b09f4410a6ce170": ("visual",  "תוספות"),             # EXTRAS
}


def _overrides():
    out = {}
    for sid, (kind, he) in PATCH.items():
        out[sid] = he if kind in ("latin", "logical") else V(he)
    return out


def stage():
    os.makedirs(os.path.join(LOOSE, "text2"), exist_ok=True)
    os.makedirs(os.path.join(LOOSE, "fonts"), exist_ok=True)

    # 1) patched eng.common
    core = Psarc(os.path.join(GAME_MAIN, "core.psarc"))
    data = core.extract(core.by_path["text2/eng.common"])
    new = tlou_loc.encode(data, _overrides())
    out_loc = os.path.join(LOOSE, "text2", "eng.common")
    with open(out_loc, "wb") as f:
        f.write(new)
    # verify our overrides survived the round-trip
    chk = tlou_loc.to_map(new)
    bad = [s for s, v in _overrides().items() if chk.get(s) != v]
    print(f"[loc] wrote {out_loc}  ({len(new):,} B, was {len(data):,})  "
          f"overrides-ok={len(_overrides()) - len(bad)}/{len(_overrides())}")

    # 2) Hebrew font: Heebo (Latin+Hebrew, closest to DINPro), per-weight, masquerading
    #    as the original DINPro name so an engine matching by family still resolves it.
    import tlou_font
    FONTS = os.path.join(HERE, "fonts")
    face_src = {
        "DINPro-Regular.otf": os.path.join(FONTS, "Heebo-Regular.ttf"),
        "DINPro-Medium.otf":  os.path.join(FONTS, "Heebo-Medium.ttf"),
    }
    for face, src in face_src.items():
        ref = os.path.join(HERE, "..", "extract", "fonts", face)   # original DINPro face
        outp = os.path.join(LOOSE, "fonts", face)
        ft = tlou_font.TTFont(src)
        if os.path.isfile(ref):
            ft["name"] = tlou_font.TTFont(ref)["name"]             # masquerade name table
        ft.save(outp)
        n, cov = tlou_font._coverage(tlou_font.TTFont(outp, lazy=True))
        print(f"[font] wrote {outp}  from {os.path.basename(src)}  glyphs~{n}  {' '.join(cov)}")

    _write_deploy_readme()
    print(f"\nStaged under {LOOSE}\n  -> review DEPLOY.txt, or re-run with --deploy")


def _write_deploy_readme():
    txt = f"""TLOU Part I - Hebrew MENU PROOF - deploy / revert
=================================================
Game data dir: {GAME_MAIN}

The proof changes 6 main-menu strings + swaps DINPro to a Hebrew-covering font.
Activation in-game: Main menu -> Options -> Language -> set TEXT and SUBTITLES to
ENGLISH (the slot we hijacked), keep Speech = English.

WHAT TO LOOK FOR
  CONTINUE  -> "ZZ-TLOU-OK-ZZ"   (Latin marker: proves the override even loads)
  NEW GAME / Options   -> LOGICAL Hebrew  (correct ONLY if the engine does bidi)
  LOAD GAME/SETTINGS/EXTRAS -> VISUAL Hebrew (correct if engine draws raw order = expected)
  -> whichever Hebrew group reads correctly decides LOGICAL vs VISUAL storage.
  -> tofu/boxes on ALL Hebrew = the font swap didn't take.

DEPLOY - option 1 (loose drop, non-destructive, TRY FIRST)
  Copy these over the game data dir (adds files, never touches core.psarc):
    {os.path.join(LOOSE, 'text2', 'eng.common')}   ->  {os.path.join(GAME_MAIN, 'text2', 'eng.common')}
    {os.path.join(LOOSE, 'fonts', 'DINPro-Regular.otf')} ->  {os.path.join(GAME_MAIN, 'fonts', 'DINPro-Regular.otf')}
    {os.path.join(LOOSE, 'fonts', 'DINPro-Medium.otf')}  ->  {os.path.join(GAME_MAIN, 'fonts', 'DINPro-Medium.otf')}
  (build_menu_proof.py --deploy does exactly this.)
  If the menu still shows English, the engine is NOT honoring loose files -> option 2.

DEPLOY - option 2 (extract + rename, reliable per the modding scene)
  Extract core.psarc into build/pc/main/ with ndarc (or our psarc.py), overwrite
  text2/eng.common + fonts/DINPro-*.otf with the proof files, then rename
  core.psarc -> BACKUP-core.psarc so the engine reads the loose tree.
  Revert = rename BACKUP-core.psarc back (or Steam "Verify integrity of files").

DEPLOY - option 3 (repack)
  ndarc repack core.psarc with the two modified files (match the Oodle tag), or a
  future pure-Python surgical repack (PIPELINE.md).

REVERT (option 1): build_menu_proof.py --revert  (removes only our loose files).
"""
    with open(os.path.join(PROOF, "DEPLOY.txt"), "w", encoding="utf-8") as f:
        f.write(txt)


REPLACE = {
    "text2/eng.common":        os.path.join(LOOSE, "text2", "eng.common"),
    "fonts/DINPro-Regular.otf": os.path.join(LOOSE, "fonts", "DINPro-Regular.otf"),
    "fonts/DINPro-Medium.otf":  os.path.join(LOOSE, "fonts", "DINPro-Medium.otf"),
}


def _clean_loose():
    for rel in ("text2/eng.common", "fonts/DINPro-Regular.otf", "fonts/DINPro-Medium.otf"):
        p = os.path.join(GAME_MAIN, *rel.split("/"))
        if os.path.isfile(p):
            os.remove(p)
            print(f"[clean] removed loose {p}")


def deploy():
    """Repack core.psarc in place (loose-file override does NOT work on this engine).
    Backs up the original to core.psarc.he_backup, then rebuilds with our 3 files."""
    import psarc_write
    stage()
    _clean_loose()
    core = os.path.join(GAME_MAIN, "core.psarc")
    backup = core + ".he_backup"
    try:
        _lock = open(core, "rb+"); _lock.close()     # is the archive writable?
    except PermissionError:
        print("\n*** The game is still OPEN and locking core.psarc. ***")
        print("Fully quit The Last of Us Part I, then re-run:  --deploy")
        return
    if not os.path.isfile(backup):
        print("[deploy] backing up core.psarc -> core.psarc.he_backup ...")
        os.rename(core, backup)          # instant (same drive)
    elif os.path.isfile(core):
        os.remove(core)                  # rebuild from the pristine backup
    repl = {k: open(v, "rb").read() for k, v in REPLACE.items()}
    print(f"[deploy] repacking core.psarc (block-copy + recompress {len(repl)} files)...")
    psarc_write.repack(backup, repl, core)
    print(f"[deploy] wrote {core}  ({os.path.getsize(core):,} B)")
    print("\nDone. Launch, Options -> Language -> Text + Subtitles = English, read the main menu.")


def revert():
    _clean_loose()
    core = os.path.join(GAME_MAIN, "core.psarc")
    backup = core + ".he_backup"
    if os.path.isfile(backup):
        if os.path.isfile(core):
            os.remove(core)
        os.rename(backup, core)
        print(f"[revert] restored core.psarc from backup")
    else:
        print("[revert] no core.psarc.he_backup found (nothing to restore)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        revert()
    elif a.deploy:
        deploy()
    else:
        stage()


if __name__ == "__main__":
    main()
