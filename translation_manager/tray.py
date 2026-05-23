"""
System tray icon for the launcher.

Runs on a background daemon thread (pystray's `run_detached` model)
so it never blocks Eel's gevent loop. The icon is created from
`build_assets/app.ico` so the tray and taskbar share the same artwork.

Menu:
  - "פתח את התוכנה" → relaunches the launcher as a new subprocess and
                       exits the current one. Used after the user
                       minimised-to-tray (the previous Chromium window
                       is dead at that point so we can't just un-hide).
  - "סגור לצמיתות"  → tray.stop() + os._exit(0).

Why subprocess-relaunch instead of un-hiding a hidden window?
  Eel + Chrome `--app` mode doesn't expose a way to programmatically
  un-hide a window that the user already closed. The window IS the
  process; once it dies, only a new launch can bring it back. We trade
  a quick boot for a clean lifecycle (single instance, no zombie state).
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)


# ── Toolhelp32 child-process termination ─────────────────────
# On Windows, child processes do NOT die when their parent exits —
# so the Chrome `--app` subprocess Eel spawned for the launcher
# window stays alive (showing a 'site can't be reached' page) after
# the Python process is gone via os._exit. We use the toolhelp32
# snapshot API + TerminateProcess to take down direct children
# explicitly before we exit; that lets the tray menus actually
# close the visible launcher window.
class _ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ('dwSize',              wintypes.DWORD),
        ('cntUsage',            wintypes.DWORD),
        ('th32ProcessID',       wintypes.DWORD),
        ('th32DefaultHeapID',   ctypes.c_void_p),
        ('th32ModuleID',        wintypes.DWORD),
        ('cntThreads',          wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase',      ctypes.c_long),
        ('dwFlags',             wintypes.DWORD),
        ('szExeFile',           wintypes.WCHAR * 260),
    ]


def _kill_my_child_processes() -> None:
    """Forcefully terminate every direct child of this process.

    Best-effort: silently no-ops on non-Windows / on API failure.
    Used by the tray's 'Open' (so the relaunch doesn't end up with
    two Chromium windows) and 'Close permanently' (so the launcher's
    Chromium window actually closes when the user picks 'close').
    """
    if sys.platform != "win32":
        return
    try:
        k = ctypes.windll.kernel32
        TH32CS_SNAPPROCESS = 0x00000002
        PROCESS_TERMINATE  = 0x0001
        INVALID            = ctypes.c_void_p(-1).value
        snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == INVALID:
            return
        try:
            my_pid = os.getpid()
            entry = _ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(_ProcessEntry32W)
            if not k.Process32FirstW(snap, ctypes.byref(entry)):
                return
            while True:
                if entry.th32ParentProcessID == my_pid:
                    h = k.OpenProcess(PROCESS_TERMINATE, False,
                                      entry.th32ProcessID)
                    if h:
                        k.TerminateProcess(h, 0)
                        k.CloseHandle(h)
                if not k.Process32NextW(snap, ctypes.byref(entry)):
                    break
        finally:
            k.CloseHandle(snap)
    except Exception:                              # pragma: no cover
        pass

_icon: Optional[object] = None        # pystray.Icon — typed loosely so the
                                      # module imports cleanly when pystray
                                      # isn't installed.
_thread: Optional[threading.Thread] = None
_on_show_request: Optional[Callable[[], None]] = None
_on_quit_request: Optional[Callable[[], None]] = None


# ─────────────────────────────────────────────────────────────
def _icon_path() -> Path | None:
    """Find the launcher's .ico file (works in dev + PyInstaller bundle)."""
    candidates: list[Path] = []
    # Frozen bundle: PyInstaller sets _MEIPASS to the extraction dir.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(Path(base) / "build_assets" / "app.ico")
    # Repo / dev layout.
    here = Path(__file__).parent.parent
    candidates.append(here / "build_assets" / "app.ico")
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_icon_image():
    """Load app.ico as a PIL.Image. Falls back to a generated square if missing."""
    from PIL import Image
    p = _icon_path()
    if p is not None:
        try:
            return Image.open(p)
        except OSError as e:
            log.warning("tray: cannot open %s — %s", p, e)
    # Bare-fallback: 64x64 solid yellow square (matches brand-yellow #fff700).
    img = Image.new("RGB", (64, 64), (255, 247, 0))
    return img


# ─────────────────────────────────────────────────────────────
def _relaunch_self(restored: bool = True) -> None:
    """Spawn a fresh launcher process and quit this one.

    Used by the "Open" tray menu after the user minimised to tray, since
    we cannot revive the dead Chromium window in-process. The new
    instance picks up persisted state from disk and starts visible.

    `restored=True` (the default for every tray/single-instance relaunch)
    passes `--restored` so the new process knows it is NOT a genuine cold
    start — it shows the disk cache instantly and skips the
    refresh-on-open. Only the OS launching the exe fresh omits the flag.
    """
    extra = ["--restored"] if restored else []
    try:
        if getattr(sys, "frozen", False):
            # Frozen build: just relaunch the same exe (no --silent so it
            # opens visible). PyInstaller onedir/onefile both honour this.
            subprocess.Popen([sys.executable, *extra], close_fds=True)
        else:
            # Dev / source run: re-invoke `python main_eel.py`.
            entry = Path(sys.argv[0]).resolve()
            subprocess.Popen([sys.executable, str(entry), *extra], close_fds=True)
    except Exception as e:                                # pragma: no cover
        log.warning("tray: relaunch failed — %s", e)


def _menu_open(icon, _item) -> None:
    """Fired by tray menu → 'פתח את התוכנה' (also bound to default-click).

    Order matters for a smooth UX:
      1. Kill any old Chrome --app child so we don't end up with two
         launcher windows after the relaunch.
      2. Spawn the new launcher subprocess FIRST so its tray icon
         appears as quickly as possible — minimises the visual gap.
      3. Sleep briefly so the new tray icon has time to show before we
         take ours away. Without this the user sees their tray icon
         vanish and only re-appear 1-2 s later (the "the icon
         disappears and the app reloads" complaint).
    """
    if _on_show_request is not None:
        try: _on_show_request()
        except Exception as e: log.warning("tray show callback failed — %s", e)
    _kill_my_child_processes()
    _relaunch_self()
    try:
        time.sleep(1.2)        # overlap with the new tray to mask the gap
    except Exception:
        pass
    try: icon.stop()
    except Exception: pass
    os._exit(0)


def _menu_quit(icon, _item) -> None:
    """Fired by tray menu → 'סגור לצמיתות'.

    Close the Chrome `--app` child FIRST — on Windows it does NOT die
    with the parent, so without this the user picks "close permanently"
    and the launcher window stays on screen (showing a dead Eel page).
    """
    if _on_quit_request is not None:
        try: _on_quit_request()
        except Exception as e: log.warning("tray quit callback failed — %s", e)
    _kill_my_child_processes()
    try: icon.stop()
    except Exception: pass
    os._exit(0)


# ─────────────────────────────────────────────────────────────
def start(
    title: str = "Translation Manager",
    on_show: Callable[[], None] | None = None,
    on_quit: Callable[[], None] | None = None,
) -> bool:
    """Spawn the tray icon on a daemon thread. Returns True on success.

    Safe to call multiple times — subsequent calls are no-ops while a
    tray is already running.
    """
    global _icon, _thread, _on_show_request, _on_quit_request
    if _icon is not None:
        return True

    try:
        import pystray
    except ImportError as e:
        log.warning("tray: pystray not installed (%s) — running without tray", e)
        return False

    _on_show_request = on_show
    _on_quit_request = on_quit

    image = _load_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("פתח את התוכנה", _menu_open, default=True),
        pystray.MenuItem("סגור לצמיתות",  _menu_quit),
    )
    _icon = pystray.Icon("translation-manager", image, title, menu)

    def _runner():
        try:
            log.info("tray: icon.run() starting")
            _icon.run()      # type: ignore[union-attr]
            log.info("tray: icon.run() returned")
        except Exception:
            # Full traceback — a silent tray failure is exactly the
            # "app not in the system tray" bug, so we want it diagnosable.
            log.exception("tray: icon.run() crashed")

    _thread = threading.Thread(target=_runner, daemon=True, name="tray")
    _thread.start()
    log.info("tray: started (thread spawned)")
    return True


def stop() -> None:
    """Stop the tray icon if running. Safe to call when none was started."""
    global _icon
    if _icon is None:
        return
    try:
        _icon.stop()         # type: ignore[union-attr]
    except Exception:
        pass
    _icon = None
