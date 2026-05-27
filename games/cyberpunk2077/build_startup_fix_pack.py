"""
build_startup_fix_pack.py
=========================
Builds and deploys `z_hebrew_startup_fix.archive` — a tiny override mod
that swaps Arabic startup videos with their English counterparts.

Why this exists
---------------
Our translation mod loads under the Arabic language slot so CDPR's RTL
pipeline handles the Hebrew text. Side effect: the publisher/intro splash
plays its Arabic variant on boot. That file is per-language inside
`basegame_1_engine.archive`:
  base\\movies\\fullscreen\\common\\cyberpunk2077_game_intro_message_ar.bk2
  base\\movies\\fullscreen\\common\\cyberpunk2077_game_intro_message_en.bk2

This script:
  1. Extracts the English video from the base archive.
  2. Places it at the SAME path as the Arabic one in a project tree.
  3. Packs that single-file tree into z_hebrew_startup_fix.archive.
  4. Deploys to the game's mod folder.

When the game boots in Arabic mode, the mod's `*_ar.bk2` entry overrides
the basegame's — and the English video plays.

NOTE on coverage
----------------
Only ONE Arabic-suffixed startup file exists across the engine archives
(verified via `WolvenKit.CLI archiveinfo -l`). The CDPR logo, epilepsy
warning, and legal/copyright screens are NOT language-suffixed files —
they're hardcoded in inkwidgets or shared assets — so this swap trick
can only fix the publisher intro splash. Everything else needs a
different mod pipeline (UI widget override).

Requires Cyberpunk 2077 to be closed (the deploy file is overwritten).
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

# ── Paths (mirror the other pack scripts) ───────────────────────────────────
CLI         = r"C:\Users\nc528\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME        = r"C:\Users\nc528\סקריפטים\תרגום משחקים\Cyberpunk 2077"
SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
ENGINE_ARCH = os.path.join(GAME, r"archive\pc\content\basegame_1_engine.archive")

WORK         = r"C:\Users\nc528\AppData\Local\Temp\startup_fix_build"
EXTRACT_DIR  = os.path.join(WORK, "extracted")
PROJECT_SRC  = os.path.join(WORK, "project", "source", "archive")
PACKED_DIR   = os.path.join(WORK, "project", "packed", "archive", "pc", "mod")

DEPLOY      = os.path.join(GAME, r"archive\pc\mod\z_hebrew_startup_fix.archive")
LOG_FILE    = os.path.join(SCRIPTS_DIR, "build_startup_fix_pack.log")

# (source-file-in-basegame, destination-path-inside-project-tree)
# Source: the path INSIDE basegame_1_engine.archive (what we extract).
# Dest:   the path INSIDE our project tree — must match the Arabic slot
#         so the override fires when the game runs in Arabic mode.
SWAPS = [
    (
        r"base\movies\fullscreen\common\cyberpunk2077_game_intro_message_en.bk2",
        r"base\movies\fullscreen\common\cyberpunk2077_game_intro_message_ar.bk2",
    ),
]

WOLVENKIT_TIMEOUT = 600


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
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
    except Exception as e:                                  # pragma: no cover
        return False, f"EXCEPTION: {e}"


def sanity_check() -> None:
    log("STEP 0: Sanity checks")
    for p, name in [
        (CLI, "WolvenKit CLI"),
        (GAME, "Game folder"),
        (ENGINE_ARCH, "basegame_1_engine.archive"),
    ]:
        if not os.path.exists(p):
            fatal(f"missing {name}: {p}")

    # Reject if the deploy target is locked (game running).
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except PermissionError:
            fatal(f"deploy target is locked (game running?): {DEPLOY}")
    log("  all paths OK")


def clean_workdir() -> None:
    log("Cleaning workdir")
    if os.path.exists(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    os.makedirs(PROJECT_SRC, exist_ok=True)
    os.makedirs(PACKED_DIR, exist_ok=True)


def extract_one(src_path_in_archive: str) -> str:
    """Extract a single file from the engine archive using WolvenKit's
    pattern flag. Returns the absolute path of the extracted file."""
    log(f"  extract {src_path_in_archive}")
    # Pattern matches by basename; we narrow to the basename so WolvenKit's
    # glob doesn't pick up siblings.
    basename = os.path.basename(src_path_in_archive)
    ok, out = run_cli([
        "extract", ENGINE_ARCH,
        "-o", EXTRACT_DIR,
        "-w", f"*{basename}",
    ])
    if not ok:
        fatal(f"extract failed:\n{out}")
    full = os.path.join(EXTRACT_DIR, src_path_in_archive)
    if not os.path.exists(full):
        fatal(f"extract said OK but file missing: {full}\nCLI output:\n{out}")
    size = os.path.getsize(full)
    log(f"    -> {full}  ({size:,} bytes)")
    return full


def place(extracted_abs: str, dest_rel_in_project: str) -> None:
    """Copy the extracted file into the project tree at the Arabic path."""
    dest_abs = os.path.join(PROJECT_SRC, dest_rel_in_project)
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    shutil.copy2(extracted_abs, dest_abs)
    log(f"    placed -> {dest_abs}  ({os.path.getsize(dest_abs):,} bytes)")


def pack_project() -> str:
    log("STEP 2: Packing project archive with WolvenKit")
    ok, out = run_cli(["pack", PROJECT_SRC, "-o", PACKED_DIR])
    if not ok:
        fatal(f"pack failed:\n{out}")
    # WolvenKit names the output `archive.archive` regardless of input dir.
    packed = os.path.join(PACKED_DIR, "archive.archive")
    if not os.path.exists(packed):
        fatal(f"pack said OK but archive missing: {packed}\nCLI output:\n{out}")
    log(f"  packed -> {packed}  ({os.path.getsize(packed):,} bytes)")
    return packed


def deploy(packed: str) -> None:
    log("STEP 3: Deploying to game mod folder")
    os.makedirs(os.path.dirname(DEPLOY), exist_ok=True)
    prev_size = os.path.getsize(DEPLOY) if os.path.exists(DEPLOY) else 0
    shutil.copy2(packed, DEPLOY)
    new_size = os.path.getsize(DEPLOY)
    log(f"  deployed -> {DEPLOY}")
    log(f"  size: {prev_size:,} -> {new_size:,} bytes  (Δ {new_size - prev_size:+,})")


def main() -> None:
    started = time.time()
    log("=" * 70)
    log("build_startup_fix_pack starting")
    log("=" * 70)

    sanity_check()
    clean_workdir()

    log(f"STEP 1: Extract + remap {len(SWAPS)} file(s)")
    for src, dest in SWAPS:
        extracted = extract_one(src)
        place(extracted, dest)

    packed = pack_project()
    deploy(packed)

    elapsed = time.time() - started
    log("=" * 70)
    log(f"DONE — total {elapsed/60:.1f} min ({int(elapsed)}s)")
    log("=" * 70)


if __name__ == "__main__":
    main()
