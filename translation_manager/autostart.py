"""
Windows "Start with Windows" autostart hook.

Writes a value under HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
that points at the launcher exe with a `--silent` flag, so when Windows
boots the launcher comes up hidden in the system tray instead of
flashing a Chromium window in the user's face.

HKCU (current user) is used on purpose: no admin elevation required, and
the entry is per-user so it doesn't pollute system-wide registry for
other accounts on a shared machine.

Public API:
    is_enabled() -> bool
    enable()     -> tuple[ok: bool, err: str]
    disable()    -> tuple[ok: bool, err: str]
    target_command() -> str   # the command line we'd write (or write today)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# Visible name in the registry entry — also what the user sees in the
# Windows "Startup apps" Task Manager tab.
_REG_VALUE_NAME = "TranslationManager"
_REG_RUN_KEY    = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Single source of truth for the "boot the launcher hidden" CLI flag.
# main_eel.py reads this same constant when parsing argv at startup.
SILENT_FLAG = "--silent"


# ─────────────────────────────────────────────────────────────
def _exe_path() -> Path:
    """Best guess for the binary to launch at boot.

    - In a frozen PyInstaller build, `sys.executable` IS the launcher exe.
    - In dev (running `python main_eel.py`), use the absolute path to
      main_eel.py so re-running via python <script> works. The registry
      entry is more useful for the prod build, but we still want dev
      toggling to do something reasonable.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(sys.argv[0]).resolve()


def target_command() -> str:
    """Return the exact command line we would write into the Run key."""
    exe = _exe_path()
    # Quote the path so spaces / Hebrew characters survive intact.
    return f'"{exe}" {SILENT_FLAG}'


# ─────────────────────────────────────────────────────────────
def _open_run_key(write: bool):
    """Open HKCU Run key. Returns the open key handle; caller closes it."""
    import winreg  # local import — non-Windows envs would fail at module load
    flags = winreg.KEY_READ | (winreg.KEY_WRITE if write else 0)
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN_KEY, 0, flags)


def is_enabled() -> bool:
    """True iff our value exists under HKCU\\...\\Run AND matches the current exe."""
    if os.name != "nt":
        return False
    try:
        import winreg
        with _open_run_key(write=False) as k:
            existing, _ = winreg.QueryValueEx(k, _REG_VALUE_NAME)
    except (OSError, FileNotFoundError):
        return False
    # If the user moved/reinstalled the exe, the registry still has the
    # OLD path. We treat that as "stale, not enabled" so the next toggle
    # ON rewrites with the current path.
    return existing.strip().strip('"') in target_command()


def enable() -> tuple[bool, str]:
    """Write/refresh the HKCU Run entry. Idempotent."""
    if os.name != "nt":
        return False, "autostart-not-supported-on-this-os"
    try:
        import winreg
        with _open_run_key(write=True) as k:
            winreg.SetValueEx(k, _REG_VALUE_NAME, 0, winreg.REG_SZ, target_command())
        return True, ""
    except OSError as e:
        log.warning("autostart: enable failed — %s", e)
        return False, str(e)


def disable() -> tuple[bool, str]:
    """Remove the HKCU Run entry. Idempotent (missing → no-op success)."""
    if os.name != "nt":
        return False, "autostart-not-supported-on-this-os"
    try:
        import winreg
        with _open_run_key(write=True) as k:
            try:
                winreg.DeleteValue(k, _REG_VALUE_NAME)
            except FileNotFoundError:
                pass
        return True, ""
    except OSError as e:
        log.warning("autostart: disable failed — %s", e)
        return False, str(e)
