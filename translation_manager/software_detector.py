"""
Local-presence detection for the Software catalog (Steam, future tools).

Each catalog id is mapped to a set of "fingerprints" — concrete paths
on disk and/or Windows registry keys. If any fingerprint resolves to an
existing target, the software is considered installed.

Returns a dict keyed by catalog id:
    {
      "steam": {
        "installed": True,
        "path":      "C:\\Program Files (x86)\\Steam",
        "exe":       "C:\\Program Files (x86)\\Steam\\steam.exe",
        "source":    "registry"   # how we found it
      },
      ...
    }

Currently only Steam has detection rules. Add new entries to FINGERPRINTS
and they'll be picked up by `scan_all()` automatically.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SoftwareFingerprint:
    """One way to recognise that a piece of software is installed."""
    paths:     tuple[str, ...] = ()   # absolute filesystem candidates
    reg_keys:  tuple[tuple[str, str, str], ...] = ()
    # reg_keys: (hive, sub_key, value_name) — hive ∈ {"HKLM", "HKCU"}.
    exe_name:  str = ""               # used to fill the "exe" field once a base is found


FINGERPRINTS: dict[str, list[SoftwareFingerprint]] = {
    "steam": [
        SoftwareFingerprint(
            paths=(
                r"C:\Program Files (x86)\Steam\steam.exe",
                r"C:\Program Files\Steam\steam.exe",
                r"D:\Steam\steam.exe",
            ),
            reg_keys=(
                ("HKCU", r"Software\Valve\Steam", "SteamExe"),
                ("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                ("HKLM", r"SOFTWARE\Valve\Steam",             "InstallPath"),
            ),
            exe_name="steam.exe",
        ),
    ],
}


# ─────────────────────────────────────────────────────────────
def _read_registry(hive: str, sub: str, name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    root = winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, name)
            return str(val) if val else None
    except (OSError, FileNotFoundError):
        return None


def _detect_one(fps: list[SoftwareFingerprint]) -> dict | None:
    for fp in fps:
        # Pass 1: direct file paths.
        for p in fp.paths:
            if Path(p).exists():
                return {
                    "installed": True,
                    "path":      str(Path(p).parent),
                    "exe":       str(Path(p)),
                    "source":    "path",
                }
        # Pass 2: registry hints. The value can be either an exe path or
        # an install directory — try both.
        for hive, sub, name in fp.reg_keys:
            val = _read_registry(hive, sub, name)
            if not val:
                continue
            candidate = Path(val)
            if candidate.is_file():
                return {
                    "installed": True,
                    "path":      str(candidate.parent),
                    "exe":       str(candidate),
                    "source":    "registry",
                }
            if candidate.is_dir():
                exe = candidate / fp.exe_name if fp.exe_name else None
                return {
                    "installed": True,
                    "path":      str(candidate),
                    "exe":       str(exe) if exe and exe.exists() else "",
                    "source":    "registry",
                }
    return None


def detect(software_id: str) -> dict:
    """Detect a single id. Always returns a dict (never raises)."""
    fps = FINGERPRINTS.get(software_id)
    if not fps:
        return {"installed": False, "path": "", "exe": "", "source": "no-rules"}
    found = _detect_one(fps)
    if found:
        return found
    return {"installed": False, "path": "", "exe": "", "source": "not-found"}


def scan_all(software_ids: list[str] | None = None) -> dict[str, dict]:
    """Run detection across all (or the given subset of) catalog ids."""
    ids = software_ids if software_ids is not None else list(FINGERPRINTS.keys())
    out: dict[str, dict] = {}
    for sid in ids:
        try:
            out[sid] = detect(sid)
        except Exception as e:  # pragma: no cover — defensive
            log.warning("software_detector: %s failed — %s", sid, e)
            out[sid] = {"installed": False, "path": "", "exe": "", "source": f"error:{e}"}
    return out
