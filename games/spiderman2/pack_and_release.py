"""pack_and_release.py — package the Spider-Man 2 Hebrew UI mod and (optionally)
publish a GitHub Release.

Bundles the two deployable Overstrike mods + the Hebrew install guide into one
zip, computes its SHA-256, and writes manifest.json (consumed by the launcher
via the Cloudflare Worker, same shape as the Steam/CP2077 packs).

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to today's date (YYYY.MM.DD). Tag = v<version>-beta.
Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys, time, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/spiderman2-hebrew-mods"   # create once: gh repo create --private
ARCHIVE_NAME = "spiderman2_hebrew_ui.zip"

ROOT    = Path(__file__).resolve().parent
MOD_DIR = ROOT / "mod"
OUT_DIR = ROOT / "release"

# Exactly the files an end user installs (the two live mods + the guide).
FILES = [
    (MOD_DIR / "hebrew_full.modular",    "hebrew_full.modular"),
    (MOD_DIR / "hebrew_font_v7.modular", "hebrew_font_v7.modular"),
    (ROOT / "release_readme_he.txt",     "קרא_אותי.txt"),
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
    version = positional[0] if positional else time.strftime("%Y.%m.%d")
    tag = f"v{version}-beta"

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
            print(f"  + {arc:28} ({real.stat().st_size:,} B)")

    digest = sha256_of(zip_path)
    manifest = {
        "archive_name": ARCHIVE_NAME,
        "sha256":       digest,
        "version":      version,
        "channel":      "beta",
        "scope":        "ui-only",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"zip      : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256   : {digest}")
    print(f"version  : {version}  (tag {tag})")
    print(f"manifest : {manifest_path}")

    if pack_only:
        print("\n--pack-only — GitHub release skipped.")
        print("To publish, run WITHOUT --pack-only (needs the repo to exist).")
        return 0

    notes = (
        f"Hebrew UI translation (BETA) for Marvel's Spider-Man 2 — version {version}.\n\n"
        f"UI/menus fully Hebrew (RTL). In-game subtitles/dialogue remain English.\n"
        f"Install via Overstrike; set in-game Language = Arabic.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO, "--prerelease",
           "--title", f"Spider-Man 2 Hebrew UI (beta) {version}",
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
