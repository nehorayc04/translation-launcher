"""pack_and_release.py -- package the Skyrim Hebrew translation mod and
(optionally) publish a GitHub Release. Mirrors the Corsair Cove/GoWR pack shape.

FREE, manual-download only -- NOT wired into the launcher (no Worker slug, no
Supabase games-row change). 178 loose files (Data\\Interface + Data\\Strings)
shipped with a self-contained `install.py` (auto-finds the game, backs up any
pre-existing file, `--revert`) + a Hebrew readme.

Usage:
    python pack_and_release.py [version] [--pack-only]

`version` defaults to 1.0.0-beta.1. FULL release (NOT prerelease) so GitHub
`releases/latest` resolves it. Artifacts land in ./release/.
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, sys, zipfile
from pathlib import Path

REPO         = "hebrew-translation-hub/skyrim-hebrew-mods"
ARCHIVE_NAME = "skyrim_hebrew.zip"

ROOT     = Path(__file__).resolve().parent
FULL     = ROOT / "work" / "_full"          # built payload: Interface/, Strings/
REL_SRC  = ROOT / "release_files"
OUT_DIR  = ROOT / "release"
PAYLOAD_DIRS = ["Interface", "Strings"]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_payload() -> list[str]:
    """Copy work/_full/{Interface,Strings} into release_files/ and write the
    deployed-files manifest install.py uses for --revert."""
    files: list[str] = []
    for sub in PAYLOAD_DIRS:
        src_dir = FULL / sub
        if not src_dir.is_dir():
            print(f"FATAL: built payload not found at {src_dir}\n  run work/build_full.py --deploy first")
            sys.exit(1)
        dst_dir = REL_SRC / sub
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        for f in sorted(dst_dir.iterdir()):
            if f.is_file():
                files.append(f"{sub}/{f.name}")
    (REL_SRC / "deployed_files.json").write_text(
        json.dumps(files, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return files


def main() -> int:
    raw = sys.argv[1:]
    pack_only = "--pack-only" in raw
    positional = [a for a in raw if not a.startswith("--")]
    version = positional[0] if positional else "1.0.0-beta.1"
    tag = f"v{version}"

    files = sync_payload()
    print(f"synced {len(files)} payload files -> release_files/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path      = OUT_DIR / ARCHIVE_NAME
    manifest_path = OUT_DIR / "manifest.json"

    extras = ["install.py", "קרא_אותי.txt", "deployed_files.json"]
    for fn in extras:
        if not (REL_SRC / fn).is_file():
            print(f"FATAL: missing {REL_SRC / fn}")
            return 1

    all_rel = extras + files
    print(f"packing {len(all_rel)} files -> release/{ARCHIVE_NAME}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel in all_rel:
            z.write(REL_SRC / rel, rel)

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
        f"Hebrew translation for Skyrim Special Edition / Anniversary Edition -- version {version}.\n\n"
        f"Full New-Era-2 Hebrew translation: menus, UI, quests, subtitles, dialogue, books "
        f"(99,875 lines across 79 plugins incl. all Creation Club content), plus a fully "
        f"translated launcher. 178 loose files, no .bsa touched -- Steam \"verify files\" cannot "
        f"revert it. Rides the game's default (English) locale slot -- no settings to change.\n\n"
        f"Known issue: in the opening cart-ride scene, the speaking character's name in the "
        f"subtitle sits at the wrong end of the line (cosmetic only, text itself is correct). "
        f"Will be fixed in a follow-up release.\n\n"
        f"Install: extract the zip, run `python install.py` (game closed). "
        f"Revert: `python install.py --revert`. See קרא_אותי.txt.\n\n"
        f"Free, manual download only -- not distributed through the launcher.\n\n"
        f"`{ARCHIVE_NAME}` SHA-256:\n`{digest}`"
    )

    # ensure the repo exists (first publish for this game)
    chk = subprocess.run(["gh", "repo", "view", REPO], capture_output=True, text=True)
    if chk.returncode != 0:
        print(f"\nrepo {REPO} not found -- creating it")
        create = subprocess.run(
            ["gh", "repo", "create", REPO, "--public",
             "--description", "Hebrew translation for Skyrim Special Edition / Anniversary Edition (free, manual download)"],
            capture_output=True, text=True)
        if create.returncode != 0:
            print("gh repo create FAILED:\n" + (create.stderr or create.stdout).strip())
            return 1
        print(create.stdout.strip())
        init = subprocess.run(
            ["gh", "api", f"repos/{REPO}/contents/README.md", "-X", "PUT",
             "-f", "message=init", "-f", "content=" + __import__("base64").b64encode(
                 f"# {REPO.split('/')[-1]}\n\nReleases: see the Releases tab.\n".encode()).decode()],
            capture_output=True, text=True)
        if init.returncode != 0:
            print("initial commit FAILED:\n" + (init.stderr or init.stdout).strip())
            return 1

    cmd = ["gh", "release", "create", tag, "--repo", REPO,
           "--title", f"Skyrim Hebrew {version}",
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
