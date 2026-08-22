"""pack_and_release.py - package the Borderless Gaming Hebrew translation and
(optionally) publish a GitHub Release. Mirrors the GoWR/VirtualDJ pack shape.

The mod is FREE and covers two surfaces:
  * the app interface  -> he-IL.json, dropped into the user languages folder
  * the effect editor  -> effects_he/*.json + bg_cache.py, applied by install.py
    to the compiled effect cache (the .slang sources cannot hold Hebrew)

Nothing is ever written into the Steam install folder.

Usage:
    python pack_and_release.py [version] [--pack-only]

FULL release (NOT prerelease) so GitHub `releases/latest` - which the Worker
reads - resolves it. Artifacts land in ./release/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "hebrew-translation-hub/borderless-gaming-hebrew-mods"
ARCHIVE_NAME = "borderless_gaming_hebrew.zip"

ROOT = Path(__file__).resolve().parent
BUILT = ROOT / "out" / "he-IL.json"
TABLES = ROOT / "effects_he"
CODEC = ROOT / "work" / "bg_cache.py"
REL_SRC = ROOT / "release_files"
OUT_DIR = ROOT / "release"

TABLE_NAMES = ("categories", "names", "descriptions", "labels", "tooltips")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    raw = sys.argv[1:]
    pack_only = "--pack-only" in raw
    positional = [a for a in raw if not a.startswith("--")]
    version = positional[0] if positional else "1.0.0-beta.1"
    tag = f"v{version}"

    if not BUILT.is_file():
        print(f"FATAL: {BUILT} missing - run work/build_hebrew.py first")
        return 1

    shutil.copy2(BUILT, REL_SRC / "he-IL.json")
    shutil.copy2(CODEC, REL_SRC / "bg_cache.py")
    (REL_SRC / "effects_he").mkdir(exist_ok=True)
    for n in TABLE_NAMES:
        shutil.copy2(TABLES / f"{n}.json", REL_SRC / "effects_he" / f"{n}.json")

    files = ["install.py", "bg_cache.py", "he-IL.json", "קרא_אותי.txt"]
    files += [f"effects_he/{n}.json" for n in TABLE_NAMES]
    for fn in files:
        if not (REL_SRC / fn).is_file():
            print(f"FATAL: missing {REL_SRC / fn}")
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    print(f"packing {len(files)} files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for fn in files:
            z.write(REL_SRC / fn, fn)
            print(f"  + {fn}")

    digest = sha256_of(zip_path)
    manifest_path.write_text(json.dumps({
        "archive_name": ARCHIVE_NAME,
        "sha256": digest,
        "version": version,
        "channel": "beta",
        "scope": "full",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nzip      : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256   : {digest}")
    print(f"version  : {version}  (tag {tag}, FULL release)")
    if pack_only:
        print("\n--pack-only - GitHub release skipped.")
        return 0

    notes = (
        f"Hebrew translation (BETA) for Borderless Gaming - version {version}. FREE.\n\n"
        f"878 strings: the full app interface (343) plus the effect editor - categories, "
        f"effect descriptions, parameter labels and tooltips (535 across 106 effects).\n\n"
        f"Installs only into %APPDATA%\\coreutils\\borderless-gaming, never into the Steam "
        f"folder, so Steam's file verification cannot revert it and no admin rights are needed.\n\n"
        f"Install: extract, run `python install.py` with the app closed. Remove: "
        f"`python install.py --revert`. Re-run after a Borderless Gaming update. "
        f"See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"Borderless Gaming Hebrew (beta) {version}",
           "--notes", notes, str(manifest_path), str(zip_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("gh release create FAILED:\n" + (proc.stderr or proc.stdout).strip())
        return 1
    print(proc.stdout.strip())
    print(f"\nRelease {tag} published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
