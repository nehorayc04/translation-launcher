#!/usr/bin/env python3
r"""
build_menu_proof.py — Phase-1 menu proof for The Last of Us Part II Remastered (Hebrew).

Closes BOTH remaining gates (bidi-storage + font) in one in-game screenshot, exactly
like the TLOU Part I / GoWR / Witcher-3 / Hogwarts proofs, and proves the whole chain
(DSAR read -> loc edit -> font swap -> plain-PSARC override -> ndmodloader mount) loads:

  CONTINUE  -> pure-LATIN marker  "ZZ-TLOU2-OK-ZZ"  -> proves the override MOUNTS + Latin renders.
  NEW GAME  -> LOGICAL Hebrew  (unreversed)   -> reads right ONLY if the ND engine does bidi.
  options   -> LOGICAL Hebrew
  LOAD GAME -> VISUAL Hebrew  (to_visual)     -> reads right if the engine draws raw byte order
  Settings  -> VISUAL Hebrew                    (expected for ND — no Arabic locale ships).
  Extras    -> VISUAL Hebrew
Whichever Hebrew group reads correctly decides LOGICAL vs VISUAL storage; tofu on ALL
Hebrew => the font swap didn't take.

Deploy = a single small plain-PSARC dropped in the game's mods\ folder (ndmodloader
mounts it above core.psarc). NON-destructive: core.psarc is never touched.

    python build_menu_proof.py            # build the override psarc under proof/
    python build_menu_proof.py --deploy   # build + copy into <game>\mods\
    python build_menu_proof.py --revert   # remove the mod from <game>\mods\

Env: TLOU2_GAME (game root), TLOU2_MODS (override mods dir, default <game>\mods).
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import tlou_loc            # noqa: E402
import tlou_rtl            # noqa: E402
import tlou_font           # noqa: E402
import psarc_write         # noqa: E402
import dsar_write          # noqa: E402
import dsar as dsar_reader  # noqa: E402
from dsar import Psarc2    # noqa: E402

GAME = os.environ.get("TLOU2_GAME", r"F:\Games\The Last of Us - Part II Remastered")
CORE = os.path.join(GAME, "build", "pc", "main", "core.psarc")
MODS = os.environ.get("TLOU2_MODS", os.path.join(GAME, "mods"))
PROOF = os.path.join(HERE, "..", "proof")
MOD_NAME = "zzz-hebrew-proof.psarc"

V = tlou_rtl.to_visual

# SID -> (kind, hebrew_logical)   kind in {latin, logical, visual}
PATCH = {
    "0023d491ee35c696": ("latin",   "ZZ-TLOU2-OK-ZZ"),   # CONTINUE  (override-mounts marker)
    "77f58b2bfe311d9c": ("logical", "משחק חדש"),           # NEW GAME
    "350b894fe0ac503c": ("logical", "אפשרויות"),           # options
    "13f31d29358aa9bd": ("visual",  "טען משחק"),            # LOAD GAME
    "7a05975ac411bd88": ("visual",  "הגדרות"),              # Settings
    "71971f150b00bfef": ("visual",  "תוספות"),              # Extras
}

FACES = {  # override face filename -> Heebo weight source
    "seriffont-Regular.otf": "Heebo-Regular.ttf",
    "seriffont-Medium.otf":  "Heebo-Medium.ttf",
}


def _overrides():
    return {sid: (he if kind in ("latin", "logical") else V(he))
            for sid, (kind, he) in PATCH.items()}


def _build_font(face, src_ttf, ref_otf):
    ft = tlou_font.TTFont(src_ttf)
    if os.path.isfile(ref_otf):
        ft["name"] = tlou_font.TTFont(ref_otf)["name"]   # masquerade as DINPro/seriffont
    import io
    buf = io.BytesIO(); ft.save(buf)
    return buf.getvalue()


def build(plain=False):
    os.makedirs(PROOF, exist_ok=True)
    core = Psarc2(CORE)

    # 1) patched eng.common (hijack the English slot)
    data = core.extract(core.by_path["text2/eng.common"])
    ov = _overrides()
    new_loc = tlou_loc.encode(data, ov)
    chk = tlou_loc.to_map(new_loc)
    bad = [s for s, v in ov.items() if chk.get(s) != v]
    print(f"[loc] eng.common patched ({len(new_loc):,} B, was {len(data):,})  overrides-ok={len(ov)-len(bad)}/{len(ov)}")

    files = {"text2/eng.common": new_loc}

    # 2) Heebo fonts masquerading as the original seriffont/DINPro faces
    fdir = os.path.join(HERE, "fonts")
    edir = os.path.join(HERE, "..", "extract", "fonts")
    for face, weight in FACES.items():
        fb = _build_font(face, os.path.join(fdir, weight), os.path.join(edir, face))
        files["fonts/" + face] = fb
        print(f"[font] fonts/{face}  <- {weight}  ({len(fb):,} B)")

    # 3) plain PSARC v1.4 with STORED blocks — the PROVEN-IN-GAME mod format (2026-07-07).
    #    core.psarc holds its inner-PSARC blocks RAW (it is a DSAR: the LZ4 outer does the
    #    compression), so the TLOU2R engine MIS-DECODES a zlib inner block -> the menu shows
    #    "UNKNOWN STRING!!!" on every line. Storing raw (identical to how core.psarc holds
    #    eng.common: block-table [0*16, tail]) makes the engine read our override
    #    byte-identically. DSAR-wrapping (dsar_write) ALSO crashed; plain STORED is the one
    #    working format. `plain` is kept for signature compat but is always plain STORED now.
    inner = psarc_write.build(files, compress=False)
    out = os.path.join(PROOF, MOD_NAME)
    with open(out, "wb") as f:
        f.write(inner)
    rb = psarc_write.verify_read(inner)
    assert all(rb.get(k) == v for k, v in files.items()), "override read-back mismatch"
    print(f"[psarc] wrote {out}  (PLAIN STORED PSARC {len(inner):,} B, {len(files)} files, read-back OK)")
    return out


def deploy(plain=False):
    out = build(plain)
    if not os.path.isdir(GAME):
        print(f"\n[!] game root not found: {GAME}"); return
    os.makedirs(MODS, exist_ok=True)
    dst = os.path.join(MODS, MOD_NAME)
    import shutil
    shutil.copyfile(out, dst)
    print(f"[deploy] -> {dst}")
    print(f"""
NEXT (user):
  1. Ensure ndmodloader is installed (Nexus 'The Last of Us Part II' mod #32):
     drop winmm.dll + modloader.asi into {GAME}
     (only modloader.ini is present now — the loader binary is NOT installed yet).
  2. Make sure modloader.ini ModFolder points at:  {MODS}
     (the current ini points at a stale E:\\ path — set it to the line above, or blank
      it to use the default <install>\\mods).
  3. Launch, Options -> Language -> set TEXT + SUBTITLES = English (the hijacked slot),
     Speech = English. Read the main menu:
       CONTINUE  -> "ZZ-TLOU2-OK-ZZ"  (Latin: proves the override mounts + font loads)
       NEW GAME / options   -> LOGICAL Hebrew  (correct only if the engine does bidi)
       LOAD GAME/Settings/Extras -> VISUAL Hebrew (correct if engine draws raw order)
     -> whichever Hebrew group reads right decides LOGICAL vs VISUAL; tofu on ALL = font miss.
Revert:  python build_menu_proof.py --revert
""")


def revert():
    dst = os.path.join(MODS, MOD_NAME)
    if os.path.isfile(dst):
        os.remove(dst); print(f"[revert] removed {dst}")
    else:
        print(f"[revert] nothing at {dst}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--plain", action="store_true",
                    help="build a bare PSARC (no DSAR wrapper) — what ndmodloader expects")
    a = ap.parse_args()
    if a.revert:
        revert()
    elif a.deploy:
        deploy(a.plain)
    else:
        build(a.plain)


if __name__ == "__main__":
    main()
