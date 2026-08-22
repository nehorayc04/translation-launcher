# -*- coding: utf-8 -*-
"""Pack the Witcher 3 Hebrew mod into witcher3_hebrew.zip + manifest.json.

Loose-files package (no exe). Double-click the .bat to open the installer:
    התקנה.bat            <- double-click -> opens a plain-terminal installer
    install_console.py   <- the interactive installer
    install.py           <- core + command-line
    lib/ ...
    data/ ...
    קרא_אותי.txt

Requires Python 3.9+ on the end user's machine.
Usage: python pack_release.py
"""
import os, json, shutil, hashlib, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(HERE, "release")
STAGE = os.path.join(os.environ.get("TEMP", "/tmp"), "w3pkg")
ZIP = os.path.join(HERE, "witcher3_hebrew.zip")
MANIFEST = os.path.join(HERE, "manifest.json")
VERSION = "1.0.0-beta.2"

ROOT_FILES = ["התקנה.bat", "install_console.py", "install.py", "קרא_אותי.txt"]
ROOT_DIRS = ["lib", "data"]


def _copytree(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main():
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    for f in ROOT_FILES:
        shutil.copy2(os.path.join(REL, f), os.path.join(STAGE, f))
    for d in ROOT_DIRS:
        _copytree(os.path.join(REL, d), os.path.join(STAGE, d))

    if os.path.exists(ZIP):
        os.remove(ZIP)
    files = []
    for root, _dirs, fns in os.walk(STAGE):
        for fn in fns:
            full = os.path.join(root, fn)
            files.append((full, os.path.relpath(full, STAGE)))
    files.sort(key=lambda x: x[1].replace("\\", "/"))
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, rel in files:
            z.write(full, rel)

    data = open(ZIP, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    # THE FIELD NAME IS PART OF THE CONTRACT: the Worker looks the release asset
    # up by `archive_name`, and mod_source.fetch_manifest REJECTS a manifest
    # without it. This packer wrote `archive` (every other game's packer writes
    # `archive_name`), which took the published mod offline in two places at once:
    # /archive answered "release has no asset 'undefined'" and the launcher raised
    # "manifest missing 'archive_name'". Keep BOTH spellings so an older launcher
    # or tool reading `archive` still works.
    json.dump({"name": "The Witcher 3 - Hebrew", "version": VERSION,
               "archive_name": "witcher3_hebrew.zip",
               "archive": "witcher3_hebrew.zip", "sha256": sha, "size": len(data)},
              open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"zip:      {ZIP}")
    print(f"size:     {len(data):,} bytes")
    print(f"sha256:   {sha}")
    print(f"files:    {len(files)}")


if __name__ == "__main__":
    main()
