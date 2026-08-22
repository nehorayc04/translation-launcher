"""pack_and_release.py -- package the Corsair Cove Hebrew translation mod
and (optionally) publish a GitHub Release. Mirrors the GoWR/SM2/WD2 pack shape.

FREE, manual-download only -- NOT wired into the launcher (no native applier,
no Worker slug). The mod is two loose paks that replace shipped empty stubs;
we ship them with a self-contained `install.py` (auto-finds the game, backs
up the originals, `--revert`) + a Hebrew readme.

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. FULL release (NOT prerelease) so GitHub
`releases/latest` resolves it. Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/corsair-cove-hebrew-mods"
ARCHIVE_NAME = "corsair_cove_hebrew.zip"

ROOT     = Path(__file__).resolve().parent
WORK     = ROOT / "work"
REL_SRC  = ROOT / "release_files"
OUT_DIR  = ROOT / "release"

PAKS = ["pakchunk0_s2-WinGDK.pak", "pakchunk0_s4-WinGDK.pak"]
SOURCES = {
    "pakchunk0_s2-WinGDK.pak": WORK / "S2_locres_full.pak",
    "pakchunk0_s4-WinGDK.pak": WORK / "S4_fonts.pak",
}


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

    for name, src in SOURCES.items():
        if not src.is_file():
            print(f"FATAL: built file not found at {src}\n  run work/build_hebrew.py --deploy first")
            return 1
        shutil.copy2(src, REL_SRC / name)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    files = ["install.py", "קרא_אותי.txt"] + PAKS
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
        print("\n--pack-only -- GitHub release skipped.")
        return 0

    notes = (
        f"Hebrew translation for Corsair Cove -- version {version}.\n\n"
        f"Full New-Era Hebrew translation: menus, UI, quests, subtitles, dialogue "
        f"(12,778 lines). Rides the game's default (English) locale slot with an "
        f"injected Hebrew font -- no settings to change, Hebrew shows up on launch.\n\n"
        f"Install: extract the zip, run `python install.py` (game closed). "
        f"Revert: `python install.py --revert`. See קרא_אותי.txt.\n\n"
        f"Free, manual download only -- not distributed through the launcher.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"Corsair Cove Hebrew {version}",
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
