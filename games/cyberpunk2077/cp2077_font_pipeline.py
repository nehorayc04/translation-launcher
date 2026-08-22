"""
cp2077_font_pipeline.py
=======================
Fully-automated WolvenKit CLI pipeline for Hebrew font replacement.

Steps:
  1. Extract original .fnt files from base game into project's source/archive/
  2. Stage cyber_hebrew.ttf as the raw input for each font (in source/raw/)
  3. Run WolvenKit.CLI import -k to rebuild .fnt with Hebrew glyph buffer
  4. Pack the project into תרגום_משחקים.archive
  5. Deploy to Cyberpunk 2077/archive/pc/mod/

Requires:
  - WolvenKit.CLI.exe at C:/Users/Nehoray_Cohen/AppData/Local/Programs/WolvenKit-CLI/
  - cyber_hebrew.ttf at PROJECT/source/archive/base/gameplay/gui/fonts/
  - .NET 8 runtime (already installed)
"""

import subprocess
import shutil
import sys
import os
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CLI = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\WolvenKit-CLI\WolvenKit.CLI.exe"
GAMEPATH = r"C:\Game Lab\Cyberpunk 2077"
PROJECT = Path(r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים")
HEBREW_TTF = PROJECT / r"source\archive\base\gameplay\gui\fonts\cyber_hebrew.ttf"
ARCHIVE_DIR = PROJECT / "source" / "archive"
RAW_DIR = PROJECT / "source" / "raw"
PACKED_OUT_DIR = PROJECT / r"packed\archive\pc\mod"
DEPLOY_TO = Path(r"C:\Game Lab\Cyberpunk 2077\archive\pc\mod\תרגום_משחקים.archive")

FONT_SOURCE_ARCHIVES = [
    Path(GAMEPATH) / r"archive\pc\content\basegame_4_gamedata.archive",
    Path(GAMEPATH) / r"archive\pc\content\basegame_1_engine.archive",
]

# Fonts to replace (paths inside the source archives)
FONTS_TO_REPLACE = [
    "base/gameplay/gui/fonts/raj/rajdhani-regular.fnt",
    "base/gameplay/gui/fonts/raj/raj-bold.fnt",
    "base/gameplay/gui/fonts/raj/raj-medium.fnt",
    "base/gameplay/gui/fonts/raj/raj-semibold.fnt",
    "base/gameplay/gui/fonts/industry/industry_demi.fnt",
]

EXTRACT_TMP = PROJECT.parent / "_font_extract_tmp"


def banner(msg):
    print("\n" + "=" * 72)
    print(f"  {msg}")
    print("=" * 72)


def run(cmd, check=True):
    pretty = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
    print(f"$ {pretty}")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.stdout:
        print(r.stdout[-1500:] if len(r.stdout) > 1500 else r.stdout)
    if r.returncode != 0:
        print(f"   stderr: {r.stderr[-500:]}")
        if check:
            print(f"\n[!] Command failed (exit {r.returncode}). Stopping.")
            sys.exit(1)
    return r


def step1_extract_originals():
    banner("Step 1 — Extract original .fnt files from base game")
    EXTRACT_TMP.mkdir(parents=True, exist_ok=True)

    needed = [f for f in FONTS_TO_REPLACE if not (ARCHIVE_DIR / f.replace("/", os.sep)).exists()]
    if not needed:
        print("  All target .fnt files already present in project — skipping extraction.")
        return

    for source_archive in FONT_SOURCE_ARCHIVES:
        # Build list of patterns for any not-yet-found fonts
        for font_path in needed[:]:
            pattern = "*" + Path(font_path).name
            run([CLI, "extract", str(source_archive), "-o", str(EXTRACT_TMP), "-w", pattern], check=False)

    # Move extracted files into project
    for font_path in FONTS_TO_REPLACE:
        target = ARCHIVE_DIR / font_path.replace("/", os.sep)
        if target.exists():
            continue
        # find in EXTRACT_TMP
        candidates = list(EXTRACT_TMP.rglob(Path(font_path).name))
        if not candidates:
            print(f"  [!] Not found: {font_path}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidates[0], target)
        print(f"  + {font_path}  ({target.stat().st_size:,} bytes)")


def step2_stage_hebrew_ttfs():
    banner("Step 2 — Stage cyber_hebrew.ttf as raw input for each font")
    if not HEBREW_TTF.exists():
        print(f"[!] Missing source font: {HEBREW_TTF}")
        sys.exit(1)
    for font_path in FONTS_TO_REPLACE:
        raw_target = RAW_DIR / font_path.replace(".fnt", ".ttf").replace("/", os.sep)
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HEBREW_TTF, raw_target)
        print(f"  + raw/{font_path.replace('.fnt', '.ttf')}")


def step3_import_ttfs():
    banner("Step 3 — Import TTFs (rebuild .fnt with Hebrew glyph buffer)")
    # Per-font import in --keep mode: stage .fnt + .ttf in same folder, run import -k
    for font_path in FONTS_TO_REPLACE:
        archive_fnt = ARCHIVE_DIR / font_path.replace("/", os.sep)
        if not archive_fnt.exists():
            print(f"  [!] Skipping (no .fnt skeleton): {font_path}")
            continue

        # Stage .ttf alongside .fnt in archive folder for -k mode
        archive_ttf = archive_fnt.with_suffix(".ttf")
        shutil.copy2(HEBREW_TTF, archive_ttf)

        size_before = archive_fnt.stat().st_size
        r = run([CLI, "import", str(archive_ttf), "-o", str(archive_fnt.parent), "-k", "-gp", GAMEPATH], check=False)
        size_after = archive_fnt.stat().st_size

        # Clean up the staged ttf — we don't want it ending up in the packed archive
        archive_ttf.unlink(missing_ok=True)

        delta = size_after - size_before
        status = "OK " if r.returncode == 0 and delta != 0 else "??"
        print(f"  [{status}] {font_path}: {size_before:,} → {size_after:,} bytes (Δ {delta:+,})")


def step4_pack():
    banner("Step 4 — Pack project into .archive")
    PACKED_OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Pack the archive directory; output goes to PACKED_OUT_DIR with name derived from input folder
    run([CLI, "pack", str(ARCHIVE_DIR), "-o", str(PACKED_OUT_DIR)])


def step5_deploy():
    banner("Step 5 — Deploy archive to game mod folder")
    # The pack command outputs an .archive named after the input folder ("archive.archive")
    # We need to find what was actually produced and copy it to the right name
    candidates = list(PACKED_OUT_DIR.glob("*.archive"))
    if not candidates:
        print(f"[!] No .archive found in {PACKED_OUT_DIR}")
        sys.exit(1)
    # Pick the most recently modified one
    src = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"  Source: {src.name}  ({src.stat().st_size:,} bytes)")

    # Rename to the project-named archive if needed
    final_name = PACKED_OUT_DIR / "תרגום_משחקים.archive"
    if src != final_name:
        shutil.copy2(src, final_name)
        print(f"  Renamed to: {final_name.name}")

    # Deploy to game folder
    DEPLOY_TO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_name, DEPLOY_TO)
    print(f"  Deployed → {DEPLOY_TO}")


def main():
    if not Path(CLI).exists():
        print(f"[!] WolvenKit.CLI.exe not found at {CLI}")
        sys.exit(1)
    if not Path(GAMEPATH).exists():
        print(f"[!] Game path not found at {GAMEPATH}")
        sys.exit(1)

    step1_extract_originals()
    step2_stage_hebrew_ttfs()
    step3_import_ttfs()
    step4_pack()
    step5_deploy()

    banner("DONE — Launch the game")


if __name__ == "__main__":
    main()
