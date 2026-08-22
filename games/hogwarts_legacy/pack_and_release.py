"""pack_and_release.py — package the Hogwarts Legacy Hebrew translation mod and
(optionally) publish a GitHub Release. Mirrors the SM2/WD2/GoWR/Anno pack shape.

The mod is a single ADDITIVE UE4 override pak (`hogwarts_hebrew.pak`) — no vanilla
game file is ever touched. We ship it with a self-contained `install.py` (auto-finds
the game, drops the pak into ~mods, `--revert` deletes it) + a Hebrew readme. We zip
those, compute SHA-256, and write manifest.json.

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. FULL release (NOT prerelease) so GitHub
`releases/latest` (read by the Worker) resolves it. Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/hogwarts-legacy-hebrew-mods"   # create once: gh repo create
ARCHIVE_NAME = "hogwarts_legacy_hebrew.zip"

ROOT     = Path(__file__).resolve().parent
REL_SRC  = ROOT / "release_files"          # install.py + readme + the built pak
OUT_DIR  = ROOT / "release"


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

    files = ["install.py", "קרא_אותי.txt", "hogwarts_hebrew.pak"]
    for fn in files:
        if not (REL_SRC / fn).is_file():
            print(f"FATAL: missing {REL_SRC / fn}\n  run work/build_hebrew.py --also-enus first")
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    print(f"packing {len(files)} files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for fn in files:
            z.write(REL_SRC / fn, fn)
            print(f"  + {fn}")

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
        f"Hebrew translation (BETA) for Hogwarts Legacy — version {version}.\n\n"
        f"FULL Hebrew: menus, settings, HUD, item/quest/spell text, journal, and all "
        f"dialogue subtitles (~53,800 lines). Ships in BOTH the English and Arabic text "
        f"slots — select \"English\" in Settings -> Text Language for correct clock/menu "
        f"formatting (recommended), or leave it on the default Arabic RTL slot (no setting "
        f"needed) which also shows Hebrew. Additive override pak — no vanilla game file is "
        f"ever touched, so store file-verification can never revert it.\n\n"
        f"Install: extract the zip, run `python install.py` (game closed), then in-game set "
        f'Settings -> Text Language to "English" (or leave on Arabic). Voice stays English '
        f"either way. Revert: `python install.py --revert`. See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"Hogwarts Legacy Hebrew (beta) {version}",
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
