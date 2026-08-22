#!/usr/bin/env python3
r"""
build_mod.py - assemble + deploy the full TLOU Part I Hebrew mod.

Reads the delegated translation (`agent_handoff/hebrew.json` + any
`agent_handoff/hebrew_*.json` slot files, {md5key -> LOGICAL Hebrew}) keyed by
md5(en) (see build_ct_strings.py), maps each Hebrew back onto EVERY SID whose EN
matches, applies `tlou_rtl.to_visual` once per value at build time, and re-encodes
the three `text2/eng.*` loc files. Also builds the Heebo faces as
`fonts/DINPro-Regular.otf` / `-Medium.otf`. Then deploys by REPACKING core.psarc
via the surgical `psarc_write` (loose override does NOT work on this engine).

    python build_mod.py            # dry-run: report coverage + staged sizes
    python build_mod.py --deploy   # repack core.psarc (game must be CLOSED)
    python build_mod.py --revert   # restore core.psarc from core.psarc.he_backup

Build reads from the PRISTINE source (core.psarc.he_backup if present, else
core.psarc) so a rebuild is always from vanilla. Deterministic.
"""
import os
import sys
import json
import glob
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import tlou_loc                       # noqa: E402
import tlou_rtl                       # noqa: E402
import tlou_font                      # noqa: E402
from psarc import Psarc              # noqa: E402
import psarc_write                    # noqa: E402

GAME_MAIN = os.environ.get(
    "TLOU_MAIN", r"D:\Games\The Last of Us - Part I\build\pc\main")
HANDOFF = os.path.join(HERE, "..", "agent_handoff")
FONTS = os.path.join(HERE, "fonts")
EXTRACT = os.path.join(HERE, "..", "extract")
SECTIONS = ["common", "subtitles", "subtitles-systemic"]     # text2/eng.<section>
SLOT = "eng"                                                 # hijacked LTR slot


def _pristine_core():
    core = os.path.join(GAME_MAIN, "core.psarc")
    backup = core + ".he_backup"
    return backup if os.path.isfile(backup) else core


def _load_en2he():
    with open(os.path.join(HANDOFF, "to_translate.json"), encoding="utf-8") as f:
        k2en = json.load(f)
    he = {}
    for p in [os.path.join(HANDOFF, "hebrew.json")] + sorted(glob.glob(os.path.join(HANDOFF, "hebrew_*.json"))):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                he.update(json.load(f))
    en2he = {}
    for k, en in k2en.items():
        h = he.get(k)
        if h:
            en2he[en] = h
    return en2he, len(k2en), len(he)


def build_loc_replacements(core, en2he):
    """-> (replacements{psarc_path: bytes}, coverage{section: (translated, total)})."""
    repl, cov = {}, {}
    for sec in SECTIONS:
        path = f"text2/{SLOT}.{sec}"
        data = core.extract(core.by_path[path])
        recs, _ = tlou_loc.decode(data)
        overrides, tr = {}, 0
        for sid, _o, en in recs:
            h = en2he.get(en)
            if h:
                overrides[f"{sid:016x}"] = tlou_rtl.to_visual(h)
                tr += 1
        repl[path] = tlou_loc.encode(data, overrides)
        cov[sec] = (tr, len(recs))
    return repl, cov


def build_font_replacements():
    repl = {}
    face_src = {"DINPro-Regular.otf": "Heebo-Regular.ttf",
                "DINPro-Medium.otf":  "Heebo-Medium.ttf"}
    for face, srcname in face_src.items():
        src = os.path.join(FONTS, srcname)
        ref = os.path.join(EXTRACT, "fonts", face)
        ft = tlou_font.TTFont(src)
        if os.path.isfile(ref):
            ft["name"] = tlou_font.TTFont(ref)["name"]
        import io
        buf = io.BytesIO(); ft.save(buf)
        repl[f"fonts/{face}"] = buf.getvalue()
    return repl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    core_path = os.path.join(GAME_MAIN, "core.psarc")
    backup = core_path + ".he_backup"

    if a.revert:
        if os.path.isfile(backup):
            if os.path.isfile(core_path):
                os.remove(core_path)
            os.rename(backup, core_path)
            print("[revert] restored core.psarc from backup")
        else:
            print("[revert] no core.psarc.he_backup")
        return

    en2he, n_keys, n_he = _load_en2he()
    src = _pristine_core()
    core = Psarc(src)
    repl, cov = build_loc_replacements(core, en2he)
    repl.update(build_font_replacements())
    core.f.close()

    tot_tr = sum(t for t, _ in cov.values())
    tot_all = sum(n for _, n in cov.values())
    print(f"translations loaded: {n_he}/{n_keys} unique EN")
    for sec in SECTIONS:
        t, n = cov[sec]
        print(f"  text2/{SLOT}.{sec:20} {t:>6}/{n:<6} SIDs Hebrew  "
              f"({len(repl[f'text2/{SLOT}.{sec}']):,} B)")
    print(f"  fonts: DINPro-Regular.otf {len(repl['fonts/DINPro-Regular.otf']):,} B, "
          f"DINPro-Medium.otf {len(repl['fonts/DINPro-Medium.otf']):,} B")
    print(f"TOTAL {tot_tr}/{tot_all} SIDs Hebrew ({100*tot_tr//max(tot_all,1)}%)")

    if not a.deploy:
        print("\n(dry-run) re-run with --deploy to repack core.psarc.")
        return

    try:
        open(core_path, "rb+").close()
    except PermissionError:
        print("\n*** Game is OPEN and locking core.psarc. Quit it, then re-run --deploy. ***")
        return
    if not os.path.isfile(backup):
        print("[deploy] backing up core.psarc -> core.psarc.he_backup ...")
        os.rename(core_path, backup)
    elif os.path.isfile(core_path):
        os.remove(core_path)
    print(f"[deploy] repacking core.psarc ({len(repl)} files replaced)...")
    psarc_write.repack(backup, repl, core_path)
    print(f"[deploy] wrote {core_path} ({os.path.getsize(core_path):,} B)")
    print("Launch, Options -> Language -> Text + Subtitles = English.")


if __name__ == "__main__":
    main()
