"""pack_and_release.py — package the Watch Dogs 2 Hebrew UI mod (interface-only)
and (optionally) publish a GitHub Release. Mirrors the SM2/CP2077 pack shape.

Bundles the deployable Hebrew loc + Hebrew font + a self-contained installer +
Hebrew guide into one zip, computes its SHA-256, and writes manifest.json
(consumed via the Cloudflare Worker, same shape as the other packs).

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. The release is a FULL release (NOT a
prerelease) so GitHub `releases/latest` — which the Worker reads — resolves it.
Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/watchdogs2-hebrew-mods"   # create once: gh repo create
ARCHIVE_NAME = "watchdogs2_hebrew_ui.zip"

ROOT     = Path(__file__).resolve().parent
SRC_DIR  = ROOT / "release_files"
OUT_DIR  = ROOT / "release"

FILES = [
    (SRC_DIR / "main_arabic.loc", "main_arabic.loc"),
    (SRC_DIR / "heb_font.ffd",    "heb_font.ffd"),
    (SRC_DIR / "heb_font.xbt",    "heb_font.xbt"),
    (SRC_DIR / "wd2_archive.py",  "wd2_archive.py"),
    (SRC_DIR / "install.py",      "install.py"),
    (SRC_DIR / "install.bat",     "install.bat"),
    (SRC_DIR / "קרא_אותי.txt",     "קרא_אותי.txt"),
]


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
    version = positional[0] if positional else "1.0.0-beta.2"
    tag = f"v{version}"

    missing = [str(p) for p, _ in FILES if not p.is_file()]
    if missing:
        print("FATAL: missing files:\n  " + "\n  ".join(missing))
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    print(f"packing {len(FILES)} files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for real, arc in FILES:
            z.write(real, arc)
            print(f"  + {arc:24} ({real.stat().st_size:,} B)")

    digest = sha256_of(zip_path)
    manifest = {
        "archive_name": ARCHIVE_NAME,
        "sha256":       digest,
        "version":      version,
        "channel":      "beta",
        "scope":        "full",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nzip      : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256   : {digest}")
    print(f"version  : {version}  (tag {tag}, FULL release)")

    if pack_only:
        print("\n--pack-only — GitHub release skipped.")
        return 0

    notes = (
        f"Hebrew translation (BETA) for Watch Dogs 2 — version {version}.\n\n"
        f"FULL Hebrew (RTL): the complete interface (menus, settings, HUD, objectives, "
        f"item/vehicle descriptions, tutorials) PLUS the spoken subtitles & dialogue "
        f"(character talk, radio chatter, NPC barks, mission narration).\n\n"
        f"Install: run `python install.py` (game CLOSED), then set Written Language = Arabic "
        f"and launch with `WatchDogs2.exe -eac_launcher`. See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"Watch Dogs 2 Hebrew (beta) {version}",
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
