r"""pack_and_release.py — package the The Last of Us Part II Remastered Hebrew mod
and (optionally) publish a GitHub Release. Mirrors the GoWR/SM2/WD2/Anno pack shape.

The mod is a SINGLE plain STORED PSARC (`zzz-hebrew.psarc`) dropped into the game's
`mods\` folder and mounted by ndmodloader above core.psarc (ADDITIVE — core.psarc
is never touched). We ship it with a self-contained `install.py` (auto-finds the
game, drops the psarc into mods\, `--revert` deletes it) + a Hebrew readme. We zip
those, compute SHA-256, and write manifest.json.

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. FULL release (NOT prerelease) so GitHub
`releases/latest` (read by the Worker) resolves it. Artifacts land in ./release/.
Prereq: run `work/build_mod.py` first (writes proof/zzz-hebrew.psarc).
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/tlou2-hebrew-mods"       # create once: gh repo create --private
ARCHIVE_NAME = "tlou2_hebrew.zip"
MOD_NAME     = "zzz-hebrew.psarc"

ROOT     = Path(__file__).resolve().parent
BUILT    = ROOT / "proof" / MOD_NAME                # the deployed/verified build (work/build_mod.py)
REL_SRC  = ROOT / "release_files"                    # install.py + readme (+ the payload we copy in)
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
        print(f"FATAL: built PSARC not found at {BUILT}\n  run work/build_mod.py first")
        return 1

    # stage the payload alongside install.py + readme
    REL_SRC.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILT, REL_SRC / MOD_NAME)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    files = ["install.py", "קרא_אותי.txt", MOD_NAME]
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
        f"Hebrew translation (BETA) for The Last of Us Part II Remastered — version {version}.\n\n"
        f"FULL Hebrew: menus, settings, accessibility, story subtitles, and background chatter. "
        f"Rides the English text slot (the game has no Arabic), stored VISUAL, with an injected "
        f"Hebrew (Heebo) font. ADDITIVE mod — a single PSARC dropped into mods\\ via ndmodloader; "
        f"core.psarc is never touched. No Denuvo / no EAC.\n\n"
        f"Install: extract the zip, run `python install.py` (game closed; ndmodloader required), then "
        f"in-game Options -> Language -> Text + Subtitles = English. Voice can stay English. "
        f"Revert: `python install.py --revert`. See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"The Last of Us Part II Hebrew (beta) {version}",
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
