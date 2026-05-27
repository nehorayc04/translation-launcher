"""
fix_engine_font_fallback.py
===========================
Engine-config override that makes EVERY Latin-font widget in the game
fall back to our patched Heebo (ara_es_nawar) instead of Arial when the
primary font is missing a glyph.

DIAGNOSIS
---------
`engine\\ink\\inkenginesettings.inkenginesettings` defines:
    fallbackFontFamilyPath = engine\\ink\\fonts\\arial.inkfontfamily
Arial is Latin-only — has zero Hebrew/Arabic glyphs. So when widgets
that specify a Latin font (industry_demi, blender, raj, orbitron, etc.)
receive Hebrew text in Arabic-mode, both the primary font AND the Arial
fallback fail → glyphs render as invisible .notdef boxes. This is what
makes the settings buttons (RESET / DEFAULTS / APPLY) appear empty.

FIX
---
Override the engine config: repoint fallbackFontFamilyPath to the
ar_es_nawar font family (which our two prior font patches loaded with
Hebrew letters + Arabic-Indic digits + Arabic punctuation aliases).
Now ALL widgets in the game get Hebrew rendering for free when their
primary Latin font lacks the glyph.

PIPELINE
--------
1. Extract pristine inkenginesettings from basegame_1_engine
2. Serialize to JSON
3. Patch the fallbackFontFamilyPath DepotPath value
4. Deserialize back to CR2W
5. Drop into project tree at engine\\ink\\inkenginesettings.inkenginesettings
6. The next rebuild/pack cycle includes this override.

Idempotent. Re-run anytime.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CLI         = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME        = r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077"
SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
ENGINE_ARCH = os.path.join(GAME, r"archive\pc\content\basegame_1_engine.archive")

PROJ_FILE   = os.path.join(
    PROJECT,
    r"source\archive\engine\ink\inkenginesettings.inkenginesettings",
)

WORK        = r"C:\Users\nc528\AppData\Local\Temp\engine_fallback_fix"
RAW_DIR     = os.path.join(WORK, "raw")
JSON_DIR    = os.path.join(WORK, "json")
ENC_DIR     = os.path.join(WORK, "encoded")

LOG_FILE    = os.path.join(SCRIPTS_DIR, "fix_engine_font_fallback.log")

# Old → New value for fallbackFontFamilyPath.DepotPath.$value
OLD_PATH = r"engine\ink\fonts\arial.inkfontfamily"
NEW_PATH = r"base\gameplay\gui\fonts\foreign\arabic\ara_es_nawar\ara_es_nawar.inkfontfamily"

WOLVENKIT_TIMEOUT = 600


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def fatal(msg: str) -> None:
    log(f"FATAL: {msg}")
    sys.exit(1)


def run_cli(args, timeout=WOLVENKIT_TIMEOUT):
    try:
        r = subprocess.run(
            [CLI] + args,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    except Exception as e:                              # pragma: no cover
        return False, f"EXCEPTION: {e}"


def main():
    log("=" * 72)
    log("fix_engine_font_fallback starting")
    log("=" * 72)

    for p, name in [(CLI, "WolvenKit CLI"), (GAME, "Game folder"),
                    (PROJECT, "Project folder"), (ENGINE_ARCH, "basegame_1_engine.archive")]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")

    shutil.rmtree(WORK, ignore_errors=True)
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)
    Path(JSON_DIR).mkdir(parents=True, exist_ok=True)
    Path(ENC_DIR).mkdir(parents=True, exist_ok=True)

    log("STEP 1: Extract pristine inkenginesettings")
    ok, out = run_cli(["extract", ENGINE_ARCH, "-o", RAW_DIR,
                       "-w", "*inkenginesettings*"])
    if not ok:
        fatal(f"extract failed:\n{out}")
    src_cr2w = os.path.join(RAW_DIR, r"engine\ink\inkenginesettings.inkenginesettings")
    if not os.path.exists(src_cr2w):
        fatal(f"extract produced no file at {src_cr2w}")
    log(f"  extracted: {src_cr2w}  ({os.path.getsize(src_cr2w):,} bytes)")

    log("STEP 2: Serialize CR2W -> JSON")
    ok, out = run_cli(["convert", "serialize", src_cr2w, "-o", JSON_DIR])
    if not ok:
        fatal(f"serialize failed:\n{out}")
    json_path = os.path.join(JSON_DIR, "inkenginesettings.inkenginesettings.json")
    if not os.path.exists(json_path):
        fatal(f"serialize produced no JSON at {json_path}")

    log("STEP 3: Patch fallbackFontFamilyPath")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    fpath = data["Data"]["RootChunk"]["fallbackFontFamilyPath"]["DepotPath"]
    old_value = fpath.get("$value")
    if old_value != OLD_PATH:
        log(f"  WARNING: expected old path {OLD_PATH!r} but found {old_value!r}")
        log(f"  proceeding anyway — will overwrite with {NEW_PATH!r}")
    fpath["$value"] = NEW_PATH
    log(f"  {old_value!r}")
    log(f"     -> {NEW_PATH!r}")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log("STEP 4: Deserialize JSON -> CR2W")
    ok, out = run_cli(["convert", "deserialize", json_path, "-o", ENC_DIR])
    if not ok:
        fatal(f"deserialize failed:\n{out}")
    enc = list(Path(ENC_DIR).glob("inkenginesettings*"))
    if not enc:
        fatal(f"no encoded output in {ENC_DIR}")
    enc_file = enc[0]
    # WolvenKit sometimes names output differently — make sure it's the expected name
    if enc_file.name != "inkenginesettings.inkenginesettings":
        target = enc_file.with_name("inkenginesettings.inkenginesettings")
        enc_file.replace(target)
        enc_file = target
    log(f"  produced: {enc_file}  ({enc_file.stat().st_size:,} bytes)")

    log("STEP 5: Place into project tree")
    os.makedirs(os.path.dirname(PROJ_FILE), exist_ok=True)
    if os.path.exists(PROJ_FILE):
        bak = PROJ_FILE + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(PROJ_FILE, bak)
            log(f"  backed up existing -> {bak}")
    shutil.copy2(str(enc_file), PROJ_FILE)
    log(f"  placed -> {PROJ_FILE}  ({os.path.getsize(PROJ_FILE):,} bytes)")

    log("=" * 72)
    log("DONE — config-override CR2W ready. Run rebuild_onscreens_and_pack.py")
    log("next to repack the deploy archive (or chain it from a wrapper).")
    log("=" * 72)


if __name__ == "__main__":
    main()
