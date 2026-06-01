"""
fix_raj_font_substitution.py
============================
Substitute the four `raj` font files with our patched Heebo FNT so the
settings menu (which references `raj.inkfontfamily`) actually renders
Hebrew. The vanilla Raj/Rajdhani files are Latin-only — Hebrew text
hits .notdef and renders invisible, which is why the RESET / DEFAULTS /
שמור שינויים buttons appeared blank.

Trade-off: Raj-using widgets (settings menu, some popups) will now show
LATIN text in Heebo's Latin design instead of Rajdhani's cyber-themed
Latin. Hebrew will render correctly via the same file's Hebrew glyphs.

Substituted paths (all 4 Raj styles → same patched Heebo binary):
  base\\gameplay\\gui\\fonts\\raj\\raj-medium.fnt
  base\\gameplay\\gui\\fonts\\raj\\raj-bold.fnt
  base\\gameplay\\gui\\fonts\\raj\\raj-semibold.fnt
  base\\gameplay\\gui\\fonts\\raj\\rajdhani-regular.fnt

Idempotent — re-run anytime to refresh from the latest patched Heebo.
Run sequence:
   1. python fix_arabic_digits_pack.py    # ensures patched FNT exists
   2. python fix_raj_font_substitution.py # copies it to Raj slots
   3. (implicit step 4 happens inside this script: pack + deploy)
"""
from __future__ import annotations

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

CLI         = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME        = r"C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Cyberpunk 2077"
SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")

# Source = our already-patched Heebo FNT (has Hebrew + Latin + Arabic-Indic
# digit aliases + punctuation aliases — full coverage for Arabic-mode UI).
SRC_FNT = os.path.join(
    PROJECT,
    r"source\archive\base\gameplay\gui\fonts\foreign\arabic\ara_es_nawar\araesnawar-regular.fnt",
)

# Targets — the 4 Raj style files the settings menu references via
# raj.inkfontfamily (Medium/Bold/Semi-Bold/Regular).
TARGETS = [
    r"source\archive\base\gameplay\gui\fonts\raj\raj-medium.fnt",
    r"source\archive\base\gameplay\gui\fonts\raj\raj-bold.fnt",
    r"source\archive\base\gameplay\gui\fonts\raj\raj-semibold.fnt",
    r"source\archive\base\gameplay\gui\fonts\raj\rajdhani-regular.fnt",
]

PROJ_PACKED = os.path.join(PROJECT, r"packed\archive\pc\mod\archive.archive")
DEPLOY      = os.path.join(GAME, r"archive\pc\mod\z_hebrew_translation.archive")
LOG_FILE    = os.path.join(SCRIPTS_DIR, "fix_raj_font_substitution.log")

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
    log("fix_raj_font_substitution starting")
    log("=" * 72)

    for p, name in [(CLI, "WolvenKit CLI"), (GAME, "Game folder"),
                    (PROJECT, "Project folder"), (SRC_FNT, "Patched Heebo FNT")]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")

    src_size = os.path.getsize(SRC_FNT)
    log(f"  source: {SRC_FNT}  ({src_size:,} bytes)")

    log("STEP 1: Copy patched FNT into all 4 Raj slots inside project tree")
    for rel in TARGETS:
        dest = os.path.join(PROJECT, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(SRC_FNT, dest)
        log(f"  placed -> {dest}  ({os.path.getsize(dest):,} bytes)")

    log("STEP 2: Pack project")
    out_dir = os.path.dirname(PROJ_PACKED)
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(PROJ_PACKED):
        os.remove(PROJ_PACKED)
    src_archive = os.path.join(PROJECT, "source", "archive")
    ok, out = run_cli(["pack", src_archive, "-o", out_dir])
    if not ok or not os.path.exists(PROJ_PACKED):
        fatal(f"pack failed:\n{out}")
    log(f"  packed: {PROJ_PACKED}  ({os.path.getsize(PROJ_PACKED):,} bytes)")

    log("STEP 3: Backup deployed archive + deploy new one")
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except PermissionError:
            fatal(f"deploy target is locked (game running?): {DEPLOY}")
        bak = DEPLOY + ".bak"
        if os.path.exists(bak):
            os.remove(bak)
        shutil.copy2(DEPLOY, bak)
        log(f"  backed up deployed -> {bak}  ({os.path.getsize(bak):,} bytes)")
    os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
    shutil.copy2(PROJ_PACKED, DEPLOY)
    log(f"  deployed -> {DEPLOY}  ({os.path.getsize(DEPLOY):,} bytes)")

    log("=" * 72)
    log("DONE — Raj font substituted with patched Heebo.")
    log("Settings menu should now render Hebrew labels.")
    log("=" * 72)


if __name__ == "__main__":
    main()
