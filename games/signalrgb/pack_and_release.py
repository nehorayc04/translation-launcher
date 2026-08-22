# -*- coding: utf-8 -*-
"""Package the SignalRGB Hebrew translation and (optionally) publish a GitHub
Release.  Mirrors the borderless-gaming / virtualdj pack shape.

    python pack_and_release.py [version] [--pack-only]

FULL release (NOT prerelease) so GitHub `releases/latest` — which the Worker
reads — resolves it.  Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "hebrew-translation-hub/signalrgb-hebrew-mods"
ARCHIVE_NAME = "signalrgb_hebrew.zip"

ROOT = Path(__file__).resolve().parent
REL = ROOT / "release_files"
OUT = ROOT / "release"

FILES = [
    "install.py", "qm.py", "patch_exe.py", "macro_scripts.py",
    "build_macros.py", "build_plugins.py",
    "hebrew.json", "macros_he.json", "plugins_he.json",
    "קרא_אותי.txt",
]


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    raw = sys.argv[1:]
    pack_only = "--pack-only" in raw
    pos = [a for a in raw if not a.startswith("--")]
    version = pos[0] if pos else "1.0.0-beta.1"
    tag = f"v{version}"

    for fn in FILES:
        if not (REL / fn).is_file():
            print("FATAL: missing", REL / fn)
            return 1

    OUT.mkdir(parents=True, exist_ok=True)
    zip_path = OUT / ARCHIVE_NAME
    manifest_path = OUT / "manifest.json"

    print(f"packing {len(FILES)} files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for fn in FILES:
            z.write(REL / fn, fn)
            print("  +", fn)

    digest = sha256_of(zip_path)
    manifest_path.write_text(json.dumps({
        "archive_name": ARCHIVE_NAME,
        "sha256": digest,
        "version": version,
        "channel": "beta",
        "scope": "full",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nzip     : {zip_path}  ({zip_path.stat().st_size:,} bytes)")
    print(f"sha256  : {digest}")
    print(f"version : {version}  (tag {tag}, FULL release)")
    if pack_only:
        print("\n--pack-only — GitHub release skipped.")
        return 0

    notes = (
        f"Hebrew translation (BETA) for SignalRGB — version {version}.\n\n"
        f"Full Hebrew UI (1,838 strings) + the Macros page (134 triggers/actions/"
        f"fields) + every device settings page (123 labels across 400+ plugins). "
        f"The UI language is set automatically.\n\n"
        f"Install: extract, close SignalRGB, run `python install.py`. "
        f"Remove: `python install.py --revert`. Re-run after a SignalRGB update. "
        f"See קרא_אותי.txt.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )
    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"SignalRGB Hebrew (beta) {version}",
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
