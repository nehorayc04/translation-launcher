"""
rebuild_onscreens_and_pack.py
=============================
End-to-end rebuild of the onscreens CR2W from the current
localization_translated.json, then pack and deploy the .archive mod.

Steps:
  1. Extract pristine onscreens.json + onscreens_final.json from
     lang_ar_text.archive (Arabic CR2W skeleton).
  2. Serialize CR2W -> text JSON (one per file).
  3. Apply current Hebrew translations (including the Breaching->טוען fix)
     via cp2077_apply_translations_to_wkit_json.py.
  4. Deserialize text JSON -> CR2W.
  5. Place CR2W files into <project>/source/archive/base/localization/ar-ar/onscreens/.
  6. Pack with WolvenKit.CLI.exe -> archive.archive.
  7. Deploy -> <game>/archive/pc/mod/z_hebrew_translation.archive.

Requires Cyberpunk 2077 to be closed (the deploy file is overwritten).
"""

import os
import sys
import subprocess
import time
import shutil

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── Paths (mirror cp2077_subtitle_batch.py) ─────────────────────────────────
CLI            = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME           = r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077"
SCRIPTS_DIR    = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT        = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
APPLY_SCRIPT   = os.path.join(SCRIPTS_DIR, "cp2077_apply_translations_to_wkit_json.py")
LANG_AR_ARCH   = os.path.join(GAME, r"archive\pc\content\lang_ar_text.archive")

WORK           = r"C:\Users\nc528\AppData\Local\Temp\onscreens_rebuild"
EXTRACT_DIR    = os.path.join(WORK, "ar_pristine")
TEXT_DIR       = os.path.join(WORK, "text")
ENCODED_DIR    = os.path.join(WORK, "encoded")

PROJ_ONSCREENS = os.path.join(PROJECT, r"source\archive\base\localization\ar-ar\onscreens")
PROJ_PACKED    = os.path.join(PROJECT, r"packed\archive\pc\mod\archive.archive")
DEPLOY         = os.path.join(GAME, r"archive\pc\mod\z_hebrew_translation.archive")

LOG_FILE       = os.path.join(SCRIPTS_DIR, "rebuild_onscreens.log")

# (CR2W filename, key in localization_translated.json)
TARGETS = [
    ("onscreens.json",        "onscreens/onscreens.json"),
    ("onscreens_final.json",  "onscreens/onscreens_final.json"),
]

WOLVENKIT_TIMEOUT = 600  # generous — pack on a 50+ MB archive can be slow
EXTRACT_TIMEOUT   = 900


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


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
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def fatal(msg):
    log(f"FATAL: {msg}")
    sys.exit(1)


def sanity_check():
    log("STEP 0: Sanity checks")
    for p, name in [
        (CLI, "WolvenKit CLI"),
        (GAME, "Game folder"),
        (PROJECT, "Project folder"),
        (LANG_AR_ARCH, "lang_ar_text.archive"),
        (APPLY_SCRIPT, "apply script"),
    ]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")
    # If a previous mod is deployed, verify it isn't locked by the game.
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except PermissionError:
            fatal(f"deploy target is locked (game running?): {DEPLOY}")
    log("  all paths OK")


def clean_workdir():
    log("Cleaning workdir")
    if os.path.exists(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    for d in (EXTRACT_DIR, TEXT_DIR, ENCODED_DIR):
        os.makedirs(d, exist_ok=True)


def step1_extract():
    log("STEP 1: Extracting pristine Arabic onscreens CR2W")
    for filename, _ in TARGETS:
        # WolvenKit glob requires wildcards on both sides; *foo* matches
        # any entry whose name contains "foo" as a literal substring.
        pattern = f"*{filename}*"
        log(f"  extract -w \"{pattern}\"")
        ok, out = run_cli(
            ["extract", LANG_AR_ARCH, "-o", EXTRACT_DIR, "-w", pattern],
            timeout=EXTRACT_TIMEOUT,
        )
        if not ok:
            fatal(f"extract failed: {out[-500:]}")
        dst = os.path.join(EXTRACT_DIR, "base", "localization", "ar-ar", "onscreens", filename)
        if not os.path.exists(dst):
            fatal(f"expected file not produced: {dst}")
        log(f"    -> {dst}  ({os.path.getsize(dst):,} bytes)")


def step2_serialize():
    log("STEP 2: Serializing CR2W -> text JSON")
    for filename, _ in TARGETS:
        src = os.path.join(EXTRACT_DIR, "base", "localization", "ar-ar", "onscreens", filename)
        log(f"  convert serialize {filename}")
        ok, out = run_cli(["convert", "serialize", src, "-o", TEXT_DIR])
        if not ok:
            fatal(f"serialize failed for {filename}: {out[-500:]}")
        # WolvenKit appends .json to the input filename
        out_txt = os.path.join(TEXT_DIR, filename + ".json")
        if not os.path.exists(out_txt):
            fatal(f"expected text JSON not produced: {out_txt}")
        log(f"    -> {out_txt}  ({os.path.getsize(out_txt):,} bytes)")


def step3_apply():
    log("STEP 3: Applying Hebrew translations (incl. Breaching->טוען fix)")
    for filename, archive_relpath in TARGETS:
        text_path = os.path.join(TEXT_DIR, filename + ".json")
        log(f"  apply translations -> {filename}")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run(
            [sys.executable, APPLY_SCRIPT, text_path, archive_relpath],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env=env,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "")[-500:]
            fatal(f"apply script failed for {filename}: {err}")
        # Echo informative lines from the apply script's output
        for line in (r.stdout or "").splitlines():
            if any(k in line for k in ("updated", "Matched", "Saved", "Loading", "[OK]")):
                log(f"    {line.strip()}")


def step4_deserialize():
    log("STEP 4: Deserializing text JSON -> CR2W")
    for filename, _ in TARGETS:
        text_path = os.path.join(TEXT_DIR, filename + ".json")
        log(f"  convert deserialize {filename}")
        ok, out = run_cli(["convert", "deserialize", text_path, "-o", ENCODED_DIR])
        if not ok:
            fatal(f"deserialize failed for {filename}: {out[-500:]}")
        out_cr2w = os.path.join(ENCODED_DIR, filename)
        if not os.path.exists(out_cr2w):
            fatal(f"expected CR2W not produced: {out_cr2w}")
        log(f"    -> {out_cr2w}  ({os.path.getsize(out_cr2w):,} bytes)")


def step5_place():
    log("STEP 5: Placing CR2W files into project archive tree")
    os.makedirs(PROJ_ONSCREENS, exist_ok=True)
    for filename, _ in TARGETS:
        src = os.path.join(ENCODED_DIR, filename)
        dst = os.path.join(PROJ_ONSCREENS, filename)
        before = os.path.getsize(dst) if os.path.exists(dst) else 0
        shutil.copy2(src, dst)
        after = os.path.getsize(dst)
        log(f"    {filename}: {before:,} -> {after:,} bytes (Δ {after - before:+,})")


def step6_pack():
    log("STEP 6: Packing project archive with WolvenKit")
    src_dir = os.path.join(PROJECT, "source", "archive")
    out_dir = os.path.dirname(PROJ_PACKED)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(PROJ_PACKED):
        os.remove(PROJ_PACKED)
    ok, out = run_cli(["pack", src_dir, "-o", out_dir], timeout=900)
    if not ok or not os.path.exists(PROJ_PACKED):
        fatal(f"pack failed: {out[-500:]}")
    log(f"  packed -> {PROJ_PACKED}  ({os.path.getsize(PROJ_PACKED):,} bytes)")


def step7_deploy():
    log("STEP 7: Deploying to game mod folder")
    os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
    before = os.path.getsize(DEPLOY) if os.path.exists(DEPLOY) else 0
    if os.path.exists(DEPLOY):
        try:
            os.remove(DEPLOY)
        except PermissionError:
            fatal("deploy target is locked. Make sure the game is closed.")
    shutil.copy2(PROJ_PACKED, DEPLOY)
    after = os.path.getsize(DEPLOY)
    log(f"  deployed -> {DEPLOY}")
    log(f"  size: {before:,} -> {after:,} bytes (Δ {after - before:+,})")


def main():
    log("=" * 70)
    log("rebuild_onscreens_and_pack starting")
    log("=" * 70)
    t0 = time.time()

    sanity_check()
    clean_workdir()
    step1_extract()
    step2_serialize()
    step3_apply()
    step4_deserialize()
    step5_place()
    step6_pack()
    step7_deploy()

    elapsed = time.time() - t0
    log("=" * 70)
    log(f"DONE — total {elapsed / 60:.1f} min ({elapsed:.0f}s)")
    log("=" * 70)


if __name__ == "__main__":
    main()
