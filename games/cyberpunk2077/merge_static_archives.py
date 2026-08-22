"""
merge_static_archives.py
========================
Merges the two STATIC Hebrew mods into a single archive:

  z_hebrew_menu_name_patch.archive  (~71 MB — Settings>Language label override)
  z_hebrew_startup_fix.archive      (~10 MB — Arabic intro video swap)
        ->  z_hebrew_static.archive (one combined archive)

Why it's safe: the two archives carry DISJOINT game paths —
  menu patch  -> base/localization/<locale>/onscreens/*
  startup fix -> base/movies/fullscreen/common/*.bk2
so extracting both into one tree and re-packing is lossless (the CR2W /
bk2 payloads are byte-identical; only the archive container is rebuilt).

What it does:
  1. Extract both deployed archives into one merged source tree.
  2. Pack the merged tree into a single archive.
  3. Back up the two old archives into mod_backups/<timestamp>/.
  4. Deploy the merged archive as z_hebrew_static.archive; remove the old two.

z_hebrew_translation.archive is NOT touched (it is the live, frequently
re-baked translation mod).

Requires Cyberpunk 2077 to be closed (the mod folder is rewritten).
Re-runnable — wipes its work dir on each invocation.
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

CLI       = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAME      = r"C:\Game Lab\Cyberpunk 2077"
MOD_DIR   = os.path.join(GAME, r"archive\pc\mod")
BACKUP_ROOT = os.path.join(GAME, r"archive\pc\mod_backups")

OLD_ARCHIVES = [
    os.path.join(MOD_DIR, "z_hebrew_menu_name_patch.archive"),
    os.path.join(MOD_DIR, "z_hebrew_startup_fix.archive"),
]
MERGED_NAME  = "z_hebrew_static.archive"
DEPLOY       = os.path.join(MOD_DIR, MERGED_NAME)

WORK        = r"C:\tmp\merge_static"
SOURCE_DIR  = os.path.join(WORK, "source", "archive")   # merged extract target
PACKED_DIR  = os.path.join(WORK, "packed")
PACKED_FILE = os.path.join(PACKED_DIR, "archive.archive")

LOG_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "merge_static_archives.log")
WKIT_TIMEOUT = 600


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


def run_cli(args, timeout=WKIT_TIMEOUT):
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


def count_files(root: str) -> int:
    return sum(1 for _, _, files in os.walk(root) for _ in files)


def step0_sanity() -> None:
    log("STEP 0: Sanity checks")
    if not os.path.exists(CLI):
        fatal(f"WolvenKit CLI missing at {CLI}")
    for arch in OLD_ARCHIVES:
        if not os.path.exists(arch):
            fatal(f"source archive missing: {arch}")
        try:
            with open(arch, "rb"):
                pass
        except OSError:
            fatal(f"source archive locked (game running?): {arch}")
    if os.path.exists(DEPLOY):
        try:
            with open(DEPLOY, "rb"):
                pass
        except OSError:
            fatal(f"deploy target locked (game running?): {DEPLOY}")
    log("  OK — both source archives present and unlocked")


def step1_clean_workdir() -> None:
    log("STEP 1: Cleaning workdir")
    if os.path.exists(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(SOURCE_DIR, exist_ok=True)
    os.makedirs(PACKED_DIR, exist_ok=True)


def step2_extract_both() -> None:
    log("STEP 2: Extracting both archives into one merged tree")
    prev = 0
    for arch in OLD_ARCHIVES:
        log(f"  extract {os.path.basename(arch)}")
        ok, out = run_cli(["extract", arch, "-o", SOURCE_DIR])
        if not ok:
            fatal(f"extract failed for {arch}:\n{out[-400:]}")
        now = count_files(SOURCE_DIR)
        delta = now - prev
        log(f"    +{delta} files  (tree now {now})")
        if delta <= 0:
            fatal(f"extract of {os.path.basename(arch)} added 0 files")
        prev = now
    log(f"  merged tree: {count_files(SOURCE_DIR)} files total")


def step3_pack() -> None:
    log("STEP 3: Packing merged tree into one archive")
    if os.path.exists(PACKED_FILE):
        os.remove(PACKED_FILE)
    ok, out = run_cli(["pack", SOURCE_DIR, "-o", PACKED_DIR])
    if not ok or not os.path.exists(PACKED_FILE):
        fatal(f"pack failed:\n{out[-400:]}")
    log(f"  packed -> {PACKED_FILE} ({os.path.getsize(PACKED_FILE):,} bytes)")


def step4_backup_and_deploy() -> None:
    log("STEP 4: Backing up old archives + deploying merged archive")
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(BACKUP_ROOT, f"static_merge_{ts}")
    os.makedirs(backup_dir, exist_ok=True)
    for arch in OLD_ARCHIVES:
        if os.path.exists(arch):
            dst = os.path.join(backup_dir, os.path.basename(arch))
            shutil.copy2(arch, dst)
            log(f"  backed up {os.path.basename(arch)} -> {dst}")

    # Deploy merged archive first (so a crash never leaves zero static mods).
    if os.path.exists(DEPLOY):
        os.remove(DEPLOY)
    shutil.copy2(PACKED_FILE, DEPLOY)
    log(f"  deployed -> {DEPLOY} ({os.path.getsize(DEPLOY):,} bytes)")

    # Now remove the two originals — their content lives in the merged archive.
    for arch in OLD_ARCHIVES:
        if os.path.exists(arch):
            os.remove(arch)
            log(f"  removed old {os.path.basename(arch)} (saved in backup)")


def main() -> None:
    t0 = time.time()
    log("=" * 74)
    log("merge_static_archives starting")
    log("=" * 74)
    step0_sanity()
    step1_clean_workdir()
    step2_extract_both()
    step3_pack()
    step4_backup_and_deploy()
    log("=" * 74)
    log(f"DONE — {(time.time()-t0)/60:.1f} min ({int(time.time()-t0)}s) — "
        f"merged into {MERGED_NAME}")
    log("=" * 74)


if __name__ == "__main__":
    main()
