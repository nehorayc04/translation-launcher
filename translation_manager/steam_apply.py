"""
Apply compiled Steam Hebrew translations to the live Steam install.

Pipeline upstream: `steam_translator.py` writes translated files under
`<repo>/steam_hebrew_output/` mirroring Steam's folder layout
(steamui/localization/*_arabic-json.js, resource/*_arabic.txt,
friends/*_arabic.txt). This module copies them into the user's actual
Steam directories (with timestamped backups of whatever was there).
"""
from __future__ import annotations

import shutil
import sys
import time
import winreg
from pathlib import Path

DEFAULT_STEAM_DIR = Path(r"C:\Program Files (x86)\Steam")


def find_steam_install() -> Path | None:
    """Locate Steam's install dir.

    Probe order:
      1. HKCU\\Software\\Valve\\Steam      ("SteamPath")
      2. HKLM\\SOFTWARE\\WOW6432Node\\Valve\\Steam  ("InstallPath")
      3. Default `C:\\Program Files (x86)\\Steam`
    A candidate must contain a `steamui/` folder to count as Steam.
    """
    candidates: list[Path] = []

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            v, _ = winreg.QueryValueEx(k, "SteamPath")
            candidates.append(Path(v))
    except OSError:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam") as k:
            v, _ = winreg.QueryValueEx(k, "InstallPath")
            candidates.append(Path(v))
    except OSError:
        pass

    candidates.append(DEFAULT_STEAM_DIR)

    for c in candidates:
        if (c / "steamui").is_dir():
            return c
    return None


def _source_dir() -> Path:
    """Where steam_hebrew_output/ lives - dev vs PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "steam_hebrew_output"
    return Path(__file__).resolve().parent.parent / "steam_hebrew_output"


def _copy_dir(src_dir: Path, dst_dir: Path, glob: str, ts: str, copied: list[str]) -> None:
    """Copy every `glob` file from src→dst, backing up existing targets first."""
    if not src_dir.is_dir() or not dst_dir.is_dir():
        return
    for f in src_dir.glob(glob):
        target = dst_dir / f.name
        if target.exists():
            backup = target.with_name(f"{target.name}.bak.{ts}")
            shutil.copy2(target, backup)
        shutil.copy2(f, target)
        copied.append(f.name)


def apply(target: Path | None = None) -> dict:
    """Copy all compiled `*_arabic*` files into the live Steam install.

    Returns the OpResult-shaped envelope:
        {"ok": bool, "count": int, "error": str|None, "steam_dir": str|None}
    """
    try:
        src = _source_dir()
        if not src.is_dir():
            return {"ok": False, "error": f"לא נמצאה תיקיית פלט: {src}"}

        steam = target or find_steam_install()
        if steam is None:
            return {"ok": False, "error": "לא נמצאה תיקיית Steam - האם Steam מותקן?"}

        ts = time.strftime("%Y%m%d_%H%M%S")
        copied: list[str] = []

        # Modern UI bundles
        _copy_dir(
            src / "steamui" / "localization",
            steam / "steamui" / "localization",
            "*_arabic-json.js", ts, copied,
        )
        # Legacy VDF - two locations
        _copy_dir(src / "resource", steam / "resource", "*_arabic.txt", ts, copied)
        _copy_dir(src / "friends",  steam / "friends",  "*_arabic.txt", ts, copied)

        if not copied:
            return {
                "ok": False,
                "error": "לא נמצאו קבצי תרגום מוכנים - הרץ את steam_translator.py קודם.",
            }

        return {"ok": True, "count": len(copied), "steam_dir": str(steam), "error": None}

    except PermissionError as e:
        where = e.filename or "Steam"
        return {"ok": False, "error": f"אין הרשאת כתיבה ל-{where}. סגור את Steam ונסה שוב."}
    except OSError as e:
        return {"ok": False, "error": str(e)}
