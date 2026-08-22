"""
pack_cp2077_mod.py — package the Cyberpunk 2077 Hebrew mod and publish a
GitHub Release to the private `cp2077-hebrew-mods` repo.

Sibling of `pack_and_release.py` (the Steam packer). Steps:
  1. Collect the two mod archives from the staging game folder.
  2. Zip them — the zip's internal layout mirrors the game tree
     (`archive/pc/mod/*.archive`), so the launcher can extract straight
     into the Cyberpunk 2077 install folder and a manual installer can
     drop the zip's contents into the game root as-is.
  3. Compute the zip's SHA-256.
  4. Write `manifest.json` — {archive_name, sha256, version}.
  5. `gh release create <tag>` on the repo, attaching both assets
     (unless `--pack-only`).

Usage:
    python pack_cp2077_mod.py [version] [--pack-only]

`version` defaults to today's date as YYYY.MM.DD. The release tag is
`v<version>`. Artifacts are written to `./release_cp2077/`.

NOTE: do NOT publish the GitHub release as a "prerelease" — the
Cloudflare Worker resolves `releases/latest`, which skips prereleases.
Beta status is conveyed via the site `games.status='beta'` field.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/cp2077-hebrew-mods"
ARCHIVE_NAME = "cyberpunk_hebrew_translation.zip"

ROOT       = Path(__file__).resolve().parent

_REPO_ROOT = ROOT.parent.parent   # games/<game>/ -> repo root
# The mod's archives live in the project's staging game copy — the folder the
# bake scripts deploy to (GAME = "Game Lab/Cyberpunk 2077"; see the "DEPLOY
# TARGET" note in CLAUDE.md — staging, NOT C:\Games).
MOD_DIR    = _REPO_ROOT / "Game Lab" / "Cyberpunk 2077" / "archive" / "pc" / "mod"
OUT_DIR    = ROOT / "release"

# The exact payload — all three archives, nothing from mod_backups/.
_MOD_FILES = [
    "z_hebrew_translation.archive",   # base-game live translation (~9 MB)
    "z_hebrew_static.archive",        # menu names + Arabic intro video (~81 MB)
    "z_hebrew_dlc.archive",           # Phantom Liberty DLC translation
]
# arcname inside the zip mirrors the game's own tree.
_ZIP_PREFIX = "archive/pc/mod"


def _find_gh() -> str:
    """Resolve the GitHub CLI — it is often not on PATH on this machine."""
    found = shutil.which("gh")
    if found:
        return found
    for cand in (
        r"C:\Program Files\GitHub CLI\gh.exe",
        r"C:\Program Files (x86)\GitHub CLI\gh.exe",
    ):
        if Path(cand).is_file():
            return cand
    return "gh"   # last resort — let subprocess raise a clear error


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

    if not MOD_DIR.is_dir():
        print(f"FATAL: mod folder not found: {MOD_DIR}")
        return 1

    files: list[tuple[str, Path]] = []
    for name in _MOD_FILES:
        real = MOD_DIR / name
        if not real.is_file():
            print(f"FATAL: missing mod archive: {real}")
            return 1
        files.append((f"{_ZIP_PREFIX}/{name}", real))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    # ── 1-2. Zip (mirrors the CP2077 archive tree) ───────────────
    # The .archive files are already compressed by WolvenKit, so ZIP_STORED
    # avoids a pointless second compression pass over ~90 MB.
    print(f"packing {len(files)} archives -> release_cp2077/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
        for arc, real in files:
            z.write(real, arc)
            print(f"  + {arc}  ({real.stat().st_size:,} bytes)")

    # ── 3. SHA-256 ───────────────────────────────────────────────
    digest = sha256_of(zip_path)

    # ── 4. Manifest (same shape the Worker + mod_source.py expect) ─
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

    # ── 5. GitHub Release ────────────────────────────────────────
    gh = _find_gh()
    print(f"\ncreating GitHub release {tag} on {REPO} …")
    notes = (
        f"Hebrew translation mod for Cyberpunk 2077 (base game) — "
        f"public beta, version {version}.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`\n\n"
        f"Distributed to the Translation Launcher via the Cloudflare "
        f"Worker proxy. Activate by setting the in-game interface "
        f"language to العربية (Arabic) — the Hebrew text routes through "
        f"CDPR's RTL pipeline."
    )
    cmd = [
        gh, "release", "create", tag,
        "--repo", REPO,
        "--title", f"Cyberpunk 2077 Hebrew translation {version} (beta)",
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
