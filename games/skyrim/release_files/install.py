#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""install.py -- Skyrim Special Edition / Anniversary Edition Hebrew translation.

Deploys 178 loose files under Data\\Interface and Data\\Strings that OVERRIDE the
game's own BSA archives (Skyrim SE loads loose files ahead of any .bsa, so nothing
inside an archive is ever touched). Rides the default English text slot -- no
in-game setting to change.

USAGE
    python install.py                              # auto-detect the game, then install
    python install.py "D:\\Games\\Skyrim Special Edition"   # explicit game root
    python install.py --revert                      # remove the Hebrew files

Run with the game CLOSED.
"""
from __future__ import annotations
import json
import os
import shutil
import string
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
PAYLOAD_DIRS = ["Interface", "Strings"]     # HERE/Interface/*, HERE/Strings/* -> Data/Interface, Data/Strings
DEPLOYED_MANIFEST = HERE / "deployed_files.json"   # list of "Interface/x" / "Strings/y" relative paths

COMMON_SUFFIXES = [
    r"Steam\steamapps\common\Skyrim Special Edition",
    r"SteamLibrary\steamapps\common\Skyrim Special Edition",
    r"GOG Games\Skyrim Anniversary Edition",
    r"GOG Games\Skyrim Special Edition",
    r"Skyrim Special Edition",
    r"Skyrim Anniversary Edition",
]


def is_game(root: Path) -> bool:
    return (root / "SkyrimSE.exe").is_file() and (root / "Data").is_dir()


def _steam_libraries() -> list[Path]:
    libs: list[Path] = []
    roots = [Path(r"C:/Program Files (x86)/Steam")]
    try:
        import winreg
        for hive, key, val in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key) as k:
                    roots.append(Path(winreg.QueryValueEx(k, val)[0]))
            except Exception:
                pass
    except Exception:
        pass
    for sr in roots:
        libs.append(sr / "steamapps" / "common")
        vdf = sr / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                import re
                for m in re.finditer(r'"path"\s*"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                    libs.append(Path(m.group(1).replace("\\\\", "/")) / "steamapps" / "common")
            except Exception:
                pass
    return libs


def find_game(argpath: str | None) -> Path | None:
    cands: list[Path] = []
    if argpath:
        cands.append(Path(argpath))
    for lib in _steam_libraries():
        cands.append(lib / "Skyrim Special Edition")
    for base in (r"C:\Program Files (x86)", r"C:\Games", r"D:\Games", r"E:\Games",
                 r"F:\Games", r"C:\GOG Games", r"D:\GOG Games"):
        for suf in COMMON_SUFFIXES:
            cands.append(Path(base) / suf if not suf.startswith(("Steam", "SteamLibrary", "GOG")) else Path(base.split(":")[0] + ":\\") / suf)
    seen = set()
    for c in cands:
        key = str(c).lower()
        if key in seen:
            continue
        seen.add(key)
        if is_game(c):
            return c
    # last resort: shallow scan of fixed drives for SkyrimSE.exe
    for d in string.ascii_uppercase:
        base = Path(f"{d}:\\")
        if not base.is_dir():
            continue
        for r, dirs, _ in os.walk(base):
            rp = Path(r)
            if len(rp.relative_to(base).parts) > 5:
                dirs[:] = []
                continue
            if is_game(rp):
                return rp
    return None


def _load_deployed_list() -> list[str]:
    if DEPLOYED_MANIFEST.is_file():
        return json.loads(DEPLOYED_MANIFEST.read_text(encoding="utf-8"))
    files = []
    for sub in PAYLOAD_DIRS:
        src_dir = HERE / sub
        if not src_dir.is_dir():
            continue
        for f in sorted(src_dir.iterdir()):
            if f.is_file():
                files.append(f"{sub}/{f.name}")
    return files


def install(root: Path) -> int:
    data = root / "Data"
    files = _load_deployed_list()
    if not files:
        print("FATAL: no payload files found next to install.py (re-extract the zip).")
        return 1

    n_installed = n_backed_up = 0
    for rel in files:
        src = HERE / rel
        if not src.is_file():
            print(f"  ! missing from package: {rel}")
            continue
        dst = data / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        bak = dst.with_suffix(dst.suffix + ".he_backup")
        if dst.is_file() and not bak.is_file():
            shutil.copy2(dst, bak)
            n_backed_up += 1
        shutil.copy2(src, dst)
        n_installed += 1

    print(f"\nInstalled {n_installed}/{len(files)} file(s) into {data}")
    if n_backed_up:
        print(f"({n_backed_up} pre-existing file(s) backed up as *.he_backup)")
    print("\nDone. Launch the game -- Hebrew is on by default (no menu changes needed).")
    return 0


def revert(root: Path) -> int:
    data = root / "Data"
    files = _load_deployed_list()
    n_removed = n_restored = 0
    for rel in files:
        dst = data / rel
        bak = dst.with_suffix(dst.suffix + ".he_backup")
        if bak.is_file():
            shutil.copy2(bak, dst)
            os.remove(bak)
            n_restored += 1
        elif dst.is_file():
            os.remove(dst)
            n_removed += 1
    print(f"Removed {n_removed} Hebrew file(s), restored {n_restored} original file(s).")
    return 0


def main() -> int:
    args = sys.argv[1:]
    do_revert = "--revert" in args
    args = [a for a in args if not a.startswith("--")]
    argpath = args[0] if args else None

    root = find_game(argpath)
    if not root:
        print("Could not find the Skyrim Special Edition installation.")
        print("Run again with the game folder as an argument, e.g.:")
        print(r'  python install.py "D:\Games\Skyrim Special Edition"')
        return 1
    print(f"Game found: {root}")

    return revert(root) if do_revert else install(root)


if __name__ == "__main__":
    sys.exit(main())
