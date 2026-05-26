"""
Single-instance guard — ports the Win32 named-mutex + named-event scheme
out of main_eel.py so main_qt.py runs identical logic without dragging
in any Eel-specific imports.

Strategy (Windows only, no-op elsewhere):

  1. CreateMutexW with a stable name. If GetLastError → ERROR_ALREADY_EXISTS,
     another instance owns the mutex.
  2. Non-owner: signal the named auto-reset event "show me" and exit 0.
  3. Owner: spawn a daemon thread that waits on the same event; on signal,
     re-show the main window (callback). Used by the Start-menu shortcut
     so a second launch doesn't crash on port collision.

Why a different mutex name than the Eel build? On purpose — running the
Eel build AND the Qt build side-by-side during development must NOT
collide. The Eel build uses `..._SingleInstance_v1`; the Qt build uses
`..._SingleInstance_qt_v1`.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from ctypes import wintypes
from typing import Callable, Optional

log = logging.getLogger(__name__)

_MUTEX_NAME      = "TranslationManagerLauncher_SingleInstance_qt_v1"
_SHOW_EVENT_NAME = "TranslationManagerLauncher_ShowEvent_qt_v1"

_HANDLE: Optional[int] = None


def acquire() -> bool:
    """True iff THIS process is the first / sole instance.

    Side effect on True: keeps the mutex handle alive in a module global
    for the process lifetime."""
    global _HANDLE
    if sys.platform != "win32":
        return True
    try:
        ERROR_ALREADY_EXISTS = 183
        k = ctypes.windll.kernel32
        k.CreateMutexW.restype  = wintypes.HANDLE
        k.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        handle = k.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            return True
        if k.GetLastError() == ERROR_ALREADY_EXISTS:
            k.CloseHandle(handle)
            return False
        _HANDLE = handle
        return True
    except Exception:
        return True


def signal_show() -> None:
    """Non-owner side — wake the running instance and exit. Best-effort."""
    if sys.platform != "win32":
        return
    try:
        k = ctypes.windll.kernel32
        k.OpenEventW.restype  = wintypes.HANDLE
        k.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        EVENT_MODIFY_STATE = 0x0002
        h = k.OpenEventW(EVENT_MODIFY_STATE, False, _SHOW_EVENT_NAME)
        if h:
            k.SetEvent(h)
            k.CloseHandle(h)
    except Exception:
        pass


def start_listener(on_show: Callable[[], None]) -> None:
    """Owner side — daemon thread that fires `on_show()` whenever the
    named event is set. `on_show` runs on the listener thread, so any
    Qt UI work it does must marshal back to the GUI thread itself."""
    if sys.platform != "win32":
        return
    try:
        k = ctypes.windll.kernel32
        k.CreateEventW.restype  = wintypes.HANDLE
        k.CreateEventW.argtypes = [
            ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR,
        ]
        handle = k.CreateEventW(None, False, False, _SHOW_EVENT_NAME)
        if not handle:
            return

        def _waiter() -> None:
            INFINITE = 0xFFFFFFFF
            while True:
                k.WaitForSingleObject(handle, INFINITE)
                try:
                    on_show()
                except Exception:
                    log.exception("single-instance: on_show callback failed")

        t = threading.Thread(target=_waiter, daemon=True, name="qt-show-event-listener")
        t.start()
    except Exception:
        log.exception("single-instance: listener setup failed")
