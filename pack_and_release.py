"""
pack_and_release.py — package the translated Steam files and publish a
GitHub Release to the private `steam-hebrew-mods` repo.

Steps:
  1. Collect the 8 translated files from `steam_hebrew_output/`.
  2. Zip them — the zip's internal layout mirrors Steam's localization
     tree, so the launcher can extract straight into the Steam install.
  3. Compute the zip's SHA-256.
  4. Write `manifest.json` — {archive_name, sha256, version}.
  5. `gh release create <tag>` on the repo, attaching both assets
     (unless `--pack-only`).

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to today's date as YYYY.MM.DD. The release tag is
`v<version>`. Artifacts are written to `./release/`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO         = "nehorayc04/steam-hebrew-mods"
ARCHIVE_NAME = "steam_hebrew_translation.zip"

ROOT       = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "steam_hebrew_output"
OUT_DIR    = ROOT / "release"

# Same managed sub-trees as translation_manager/steam_mod.py — keeps the
# zip to exactly the 8 translated files (no stray .partial.json / .tmp).
_GLOBS: list[tuple[str, str]] = [
    ("steamui/localization", "*_arabic-json.js"),
    ("resource",             "*_arabic.txt"),
    ("friends",              "*_arabic.txt"),
]


def collect_files() -> list[tuple[str, Path]]:
    """[(arcname, abspath)] — arcname is the path INSIDE the zip."""
    out: list[tuple[str, Path]] = []
    for subdir, pattern in _GLOBS:
        d = SOURCE_DIR / subdir
        if d.is_dir():
            for f in sorted(d.glob(pattern)):
                out.append((f"{subdir}/{f.name}", f))
    return out


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
    version = positional[0] if positional else time.strftime("%Y.%m.%d")
    tag = f"v{version}"

    if not SOURCE_DIR.is_dir():
        print(f"FATAL: source folder not found: {SOURCE_DIR}")
        return 1
    files = collect_files()
    if not files:
        print("FATAL: no translated files found to pack")
        return 1
    if len(files) != 8:
        print(f"WARNING: expected 8 files, found {len(files)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    # ── 1-2. Zip (mirrors Steam's localization tree) ─────────
    print(f"packing {len(files)} files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, real in files:
            z.write(real, arc)
            print(f"  + {arc}")

    # ── 3. SHA-256 ───────────────────────────────────────────
    digest = sha256_of(zip_path)

    # ── 4. Manifest ──────────────────────────────────────────
    manifest = {
        "archive_name": ARCHIVE_NAME,
        "sha256":       digest,
        "version":      version,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    print()
    print(f"zip      : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256   : {digest}")
    print(f"version  : {version}")
    print(f"manifest : {manifest_path}")

    if pack_only:
        print("\n--pack-only — GitHub release skipped.")
        return 0

    # ── 5. GitHub Release ────────────────────────────────────
    print(f"\ncreating GitHub release {tag} on {REPO} …")
    notes = (
        f"Hebrew localization pack for Steam — version {version}.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`\n\n"
        f"Consumed by the Translation Launcher via the Cloudflare Worker proxy."
    )
    cmd = [
        "gh", "release", "create", tag,
        "--repo", REPO,
        "--title", f"Steam Hebrew translation {version}",
        "--notes", notes,
        str(manifest_path),
        str(zip_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("gh release create FAILED:")
        print((proc.stderr or proc.stdout).strip())
        return 1
    print(proc.stdout.strip())
    print(f"\nRelease {tag} published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
