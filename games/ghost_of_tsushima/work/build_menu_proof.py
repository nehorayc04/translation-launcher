#!/usr/bin/env python3
r"""
build_menu_proof.py — Ghost of Tsushima DC: main-menu Hebrew PROOF (Phase-1 gate closer).

Closes the two remaining Phase-1 gates in ONE in-game launch:
  * BIDI  — is the Arabic slot rendered LOGICAL (engine bidi) or VISUAL (raw)?  We patch some
            menu keys LOGICAL and some VISUAL; whichever reads correctly in-game decides.
  * FONT  — does the shipped `fOnk` font already cover Hebrew (U+05D0-05EA)?  If the Hebrew
            renders (no tofu) the font is fine; tofu => the `fOnk` glyph-injection sub-project.
A pure-Latin marker ("ZZ-GOT-OK-ZZ") on CONTINUE proves the override .psarc loads AT ALL
(font-independent), separating "override didn't load" from "font lacks Hebrew".

Mechanism (all pieces proven in Phase-1 recon):
  read English lang_english_text.xpps -> map the menu EN strings to their u64 keys
  -> surgically override those keys in lang_arabic_text.xpps (tools/xpps.patch: append+repoint)
  -> pack a tiny inner PSARC holding ONLY "/lang_arabic_text.xpps" (STORED, flags=0x0e)
  -> DSAR-wrap it (LZ4 outer) -> drop as cache_pc/psarc/zzz_hebrew_gt_proof.psarc
     (sorts AFTER gapack_misc_l.psarc -> the engine's alphabetical mount overrides the packed copy).

Activation in-game: Settings -> Options -> General -> Text Language = Arabic / العربية.
Revert: --revert (deletes the one proof psarc; the 55 shipped archives are never touched).

    python build_menu_proof.py            # build to scratchpad + re-read validate (no game touched)
    python build_menu_proof.py --deploy   # + copy the proof psarc into the game
    python build_menu_proof.py --revert   # delete the proof psarc from the game

Env override: GOT_GAME = game root (default F:/Games/Ghost of Tsushima DC).
Run with the repo .venv python (needs lz4).
"""
import os, sys, argparse, importlib.util, struct

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)                       # games/ghost_of_tsushima
REPO = os.path.dirname(os.path.dirname(GAME_DIR))      # repo root
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
GAPACK_L = os.path.join(PSARC_DIR, "gapack_misc_l.psarc")
PROOF_NAME = "gapack_misc_zhebrew.psarc"               # matches the engine's gapack_misc_* load pattern,
#   sorts AFTER gapack_misc_y (last shipped misc) -> later-mounted overrides. The exe formats "%s.psarc"
#   from a KNOWN package-name set (it does NOT scan arbitrary *.psarc), so an off-pattern name like
#   "zzz_*" is never requested/mounted (proven: zzz_ override was ignored in-game 2026-07-07). The
#   community Austronesian pack (Nexus #807) uses gapack_misc_z<lang> for exactly this reason.
INNER_PATH = "/lang_arabic_text.xpps"                  # leading slash — must match the shipping TOC key
EXTRACT = os.path.join(GAME_DIR, "extract")
SCRATCH = os.path.join(HERE, "_proof_out")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

xpps = _load("got_xpps", os.path.join(GAME_DIR, "tools", "xpps.py"))
rtl = _load("got_rtl", os.path.join(HERE, "got_rtl.py"))
dsar = _load("dsar", os.path.join(REPO, "games", "tlou2", "tools", "dsar.py"))
got_dsar = _load("got_dsar", os.path.join(HERE, "got_dsar.py"))   # FAITHFUL GoT DSAR (filler 55*7, 16-align)
psarc_write = _load("psarc_write", os.path.join(REPO, "games", "tlou2", "tools", "psarc_write.py"))

INNER_FLAGS = 0x0e   # GoT inner PSARC header flags (TLOU2 uses 0x0c) — from Phase-1 repack recon

# menu EN source string -> (Hebrew, mode). mode: "marker"=Latin proves-load; "log"=LOGICAL; "vis"=VISUAL bake.
PROOF = {
    "Continue":  ("ZZ-GOT-OK-ZZ", "marker"),   # font-independent: proves the override psarc mounts
    "New Game":  ("משחק חדש", "log"),
    "Load Game": ("טען משחק", "log"),
    "Options":   ("הגדרות", "log"),
    "Subtitles": ("כתוביות", "vis"),           # VISUAL-baked: if THIS reads right & the LOGICAL ones
    "Settings":  ("הגדרות תצוגה", "vis"),       #               read reversed -> engine is NON-bidi.
}


def _extract_live(base_name, dst):
    """Extract lang_<base>_text.xpps from the live gapack_misc_l if the staged copy is missing."""
    if os.path.exists(dst):
        return dst
    p = dsar.Psarc2(GAPACK_L)
    ent = next(e for e in p.files() if e.path.endswith(base_name))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(p.extract(ent))
    return dst


def build(fmt="plain"):
    en_path = _extract_live("/lang_english_text.xpps", os.path.join(EXTRACT, "lang_english_text.xpps"))
    ar_path = _extract_live("/lang_arabic_text.xpps",  os.path.join(EXTRACT, "lang_arabic_text.xpps"))
    en = xpps.read_pack(en_path)                 # {key_hex: text}
    en_by_text = {}
    for k, t in en.items():
        en_by_text.setdefault(t, k)              # first key wins
    overrides, report = {}, []
    for en_txt, (heb, mode) in PROOF.items():
        k = en_by_text.get(en_txt)
        if not k:
            report.append(f"  [skip] EN key not found: {en_txt!r}")
            continue
        stored = rtl.to_visual(heb) if mode == "vis" else heb
        overrides[k] = stored
        report.append(f"  [{mode:6}] {en_txt!r:14} key={k} -> {heb!r}")
    ar_data = open(ar_path, "rb").read()
    new_ar = xpps.patch(ar_data, overrides)
    print(f"patched {len(overrides)} menu keys; AR .xpps {len(ar_data)} -> {len(new_ar)} (+{len(new_ar)-len(ar_data)})")
    print("\n".join(report))
    # re-read the patched xpps to confirm the overrides landed
    back = dict(xpps.read_pack_bytes(new_ar))
    for k in overrides:
        assert back.get(k) == overrides[k], f"readback mismatch for {k}"
    print("readback OK: all overrides present in the patched .xpps")
    # pack the override archive.
    #   fmt="plain" (DEFAULT): a plain PSARC v1.4 (zlib blocks, flags=0x0e, blockSize 0x10000) —
    #       BYTE-FORMAT-IDENTICAL to the shipping music_*.psarc, which the GoT engine loads natively.
    #       The engine's DirectStorage path rejected our DSAR wrap (chunk size 256KB vs GoT's ~64KB,
    #       filler 54.55*6 vs 55*7) -> boot crash 2026-07-07 (same class as the TLOU2 "DSAR-wrapped mod
    #       crashed; plain STORED PSARC worked" lesson). Plain PSARC sidesteps all DSAR faithfulness.
    #   fmt="dsar": the old DSAR-wrapped path (kept as a fallback / for a faithful-DSAR experiment).
    os.makedirs(SCRATCH, exist_ok=True)
    out = os.path.join(SCRATCH, PROOF_NAME)
    if fmt == "dsar":
        inner = psarc_write.build({INNER_PATH: new_ar}, flags=INNER_FLAGS, compress=False)
        proof = got_dsar.wrap(inner)          # FAITHFUL GoT DSAR (filler 55*7, 16-byte-aligned, PADDING* gaps)
        open(out, "wb").write(proof)
        ps = dsar.Psarc2(out)
        rt = dict(xpps.read_pack_bytes(ps.extract(next(e for e in ps.files() if e.path == INNER_PATH))))
        print(f"proof psarc (FAITHFUL DSAR) built: {out}  ({len(proof):,} B, inner {len(inner):,} B)")
    else:
        proof = psarc_write.build({INNER_PATH: new_ar}, flags=INNER_FLAGS, compress=True)
        open(out, "wb").write(proof)
        rt = dict(xpps.read_pack_bytes(psarc_write.verify_read(proof)[INNER_PATH]))
        print(f"proof psarc (PLAIN PSARC, music-format) built: {out}  ({len(proof):,} B)")
    for k in overrides:
        assert rt.get(k) == overrides[k], f"proof-psarc readback mismatch for {k}"
    print("proof psarc re-reads OK (all overrides present)")
    return out


def deploy(fmt="plain"):
    out = build(fmt)
    dst = os.path.join(PSARC_DIR, PROOF_NAME)
    import shutil
    shutil.copyfile(out, dst)
    print(f"\nDEPLOYED -> {dst}")
    print("Launch the game, then Settings -> Options -> General -> Text Language = العربية (Arabic).")
    print("Check the main menu: CONTINUE should read 'ZZ-GOT-OK-ZZ' (proves load); the Hebrew items")
    print("tell you bidi+font. Revert with --revert.")


def revert():
    dst = os.path.join(PSARC_DIR, PROOF_NAME)
    if os.path.exists(dst):
        os.remove(dst); print(f"removed {dst}")
    else:
        print(f"nothing to revert ({dst} absent)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--plain", action="store_true", help="plain PSARC (music format) — REJECTED under gapack_misc_ names; kept for reference")
    a = ap.parse_args()
    fmt = "plain" if a.plain else "dsar"      # default = FAITHFUL GoT DSAR (the engine expects DSAR under gapack_misc_*)
    if a.revert: revert()
    elif a.deploy: deploy(fmt)
    else: build(fmt)
