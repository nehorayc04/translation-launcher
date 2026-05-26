"""
fix_all_ui_fonts.py
===================
Broad UI-font substitution. Replaces the core Cyberpunk 2077 Latin UI
font files (Blender, Industry, Orbitron, Arame) with copies of our
patched Heebo FNT so every widget that references those families now
gets Hebrew-capable glyphs.

WHY
---
Settings menu (and likely most main-menu widgets) reference Latin font
families. Those families' .fnt files contain ZERO Hebrew glyphs, so
Hebrew text renders as invisible .notdef boxes. Substituting our
patched Heebo file at those paths makes those widgets Hebrew-capable.

The patched Heebo FNT already shipped at the Arabic slot has 28 cmap
aliases for Arabic-Indic digits + punctuation, so number/percent/etc.
formatting also works after substitution.

TRADE-OFF
---------
Latin text in widgets that use these font slots will now render in
Heebo's Latin design instead of the original cyber-themed designs
(Blender Pro, Industry Demi, Orbitron). Still readable, still clean
geometric, but visually different from vanilla.

TARGETS (5 new + leaves the 4 prior Raj slots untouched)
--------------------------------------------------------
  base\\gameplay\\gui\\fonts\\blender\\book\\blenderpro-book.fnt
  base\\gameplay\\gui\\fonts\\blender\\bold\\blenderpro-bold.fnt
  base\\gameplay\\gui\\fonts\\industry\\industry_demi.fnt
  base\\gameplay\\gui\\fonts\\orbitron\\orbitron-regular.fnt
  base\\gameplay\\gui\\fonts\\arame\\regular\\arame-mono-regular.fnt

The prior Raj substitution (4 files at base\\gameplay\\gui\\fonts\\raj\\*)
remains in the project tree from fix_raj_font_substitution.py.

Idempotent — safe to re-run anytime.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CLI         = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME        = r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077"
SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")

# Source = our already-patched Heebo FNT (Hebrew + Latin + Arabic-Indic
# digit + punctuation aliases). This is the same file deployed at the
# Arabic slot.
SRC_FNT = os.path.join(
    PROJECT,
    r"source\archive\base\gameplay\gui\fonts\foreign\arabic\ara_es_nawar\araesnawar-regular.fnt",
)

# Targets — relative to <project>/. All UI font slots the engine could
# fall through to. Includes Arial (the ultimate engine-wide fallback per
# inkenginesettings.fallbackFontFamilyPath) for the nuclear "no widget
# can possibly render invisible Hebrew" coverage.
TARGETS = [
    # Existing 5 from the first run
    r"source\archive\base\gameplay\gui\fonts\blender\book\blenderpro-book.fnt",
    r"source\archive\base\gameplay\gui\fonts\blender\bold\blenderpro-bold.fnt",
    r"source\archive\base\gameplay\gui\fonts\industry\industry_demi.fnt",
    r"source\archive\base\gameplay\gui\fonts\orbitron\orbitron-regular.fnt",
    r"source\archive\base\gameplay\gui\fonts\arame\regular\arame-mono-regular.fnt",
    # New: Arial + Arame Bold — the engine-wide fallback families.
    # If even THIS doesn't make the buttons render, the issue isn't font
    # coverage at all — it's that the widgets aren't being sent text.
    r"source\archive\base\gameplay\gui\fonts\arial\regular\arial_regular.fnt",
    r"source\archive\base\gameplay\gui\fonts\arial\bold\arial_bold.fnt",
    r"source\archive\base\gameplay\gui\fonts\arame\bold\arame-mono-bold.fnt",
]

PROJ_PACKED = os.path.join(PROJECT, r"packed\archive\pc\mod\archive.archive")
DEPLOY      = os.path.join(GAME, r"archive\pc\mod\z_hebrew_translation.archive")
LOG_FILE    = os.path.join(SCRIPTS_DIR, "fix_all_ui_fonts.log")

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
    log("fix_all_ui_fonts starting")
    log("=" * 72)

    for p, name in [(CLI, "WolvenKit CLI"), (GAME, "Game folder"),
                    (PROJECT, "Project folder"), (SRC_FNT, "Patched Heebo FNT")]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")

    src_size = os.path.getsize(SRC_FNT)
    log(f"  source: {SRC_FNT}  ({src_size:,} bytes)")

    log(f"STEP 1: Copy patched FNT into {len(TARGETS)} UI font slots")
    for rel in TARGETS:
        dest = os.path.join(PROJECT, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(SRC_FNT, dest)
        log(f"  placed -> {os.path.relpath(dest, PROJECT)}  ({os.path.getsize(dest):,} bytes)")

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
    log("DONE — UI fonts substituted across all 5 slots + 4 Raj slots from prior run.")
    log("=" * 72)


if __name__ == "__main__":
    main()
