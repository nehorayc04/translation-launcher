"""pack_and_release.py — package the God of War: Ragnarök Hebrew translation mod
and (optionally) publish a GitHub Release. Mirrors the SM2/WD2/Anno pack shape.

The mod is a SINGLE localization WAD (`r_lang_ar.wad`) that replaces the game's
Arabic-slot text with full Hebrew. We ship it with a self-contained `install.py`
(auto-finds the game, backs up the original, copies the WAD, `--revert`) + a
Hebrew readme. We zip those, compute SHA-256, and write manifest.json.

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. FULL release (NOT prerelease) so GitHub
`releases/latest` (read by the Worker) resolves it. Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/godofwar-ragnarok-hebrew-mods"   # create once: gh repo create
ARCHIVE_NAME = "godofwar_ragnarok_hebrew.zip"

ROOT     = Path(__file__).resolve().parent
BUILT    = ROOT / "out" / "r_lang_ar.wad"          # the deployed/verified Hebrew build
REL_SRC  = ROOT / "release_files"                   # install.py + readme (+ the payload we copy in)
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

    if not BUILT.is_file():
        print(f"FATAL: built WAD not found at {BUILT}\n  run work/build_wad.py first")
        return 1

    # stage the payload alongside install.py + readme
    shutil.copy2(BUILT, REL_SRC / "r_lang_ar.wad")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    files = ["install.py", "קרא_אותי.txt", "r_lang_ar.wad"]
    for fn in files:
        if not (REL_SRC / fn).is_file():
            print(f"FATAL: missing {REL_SRC / fn}")
            return 1

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
        f"Hebrew translation (BETA) for God of War: Ragnarök — version {version}.\n\n"
        f"FULL Hebrew (all 48,886 strings): menus, settings, subtitles, dialogue, journal, "
        f"descriptions. Rides the Arabic RTL slot with an injected Hebrew (David) font. "
        f"No anti-cheat; only the localization WAD is touched.\n\n"
        f"Install: extract the zip, run `python install.py` (game closed), then in-game set "
        f'Settings -> Text Language to "עברית" (the renamed Hebrew option). Voice can stay English. '
        f"Revert: `python install.py --revert`. See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"God of War Ragnarök Hebrew (beta) {version}",
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
