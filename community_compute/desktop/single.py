# -*- coding: utf-8 -*-
"""Single-instance guard.

Two copies of this app are worse than useless: they share ONE worker_id and ONE
state.json, so they claim the same lines, race each other's submits, and
last-write-wins each other's counters. A background app that also lives in the
tray is especially easy to start twice by accident.

The launcher's hard-won rule applies here too: a named mutex created by an
ELEVATED process gets a default DACL that mandatory-integrity DENIES to a
medium-IL process, so the second launch fails with ERROR_ACCESS_DENIED (5), NOT
ERROR_ALREADY_EXISTS (183). Treating only 183 as "already running" fails OPEN and
you get the two-process mess anyway — so BOTH are treated as "someone owns it".
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

_MUTEX = "Local\\CommunityComputeWorker_singleton"
_EVENT = "Local\\CommunityComputeWorker_show"
ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5

_handle = None


def acquire() -> bool:
    """True = we own the instance. False = another copy is already running."""
    global _handle
    try:
        k = ctypes.windll.kernel32
        k.CreateMutexW.restype = wintypes.HANDLE
        h = k.CreateMutexW(None, wintypes.BOOL(True), _MUTEX)
        err = k.GetLastError()
        if err in (ERROR_ALREADY_EXISTS, ERROR_ACCESS_DENIED):
            return False
        _handle = h
        return True
    except OSError:
        return True          # never block a launch because the guard itself broke


def signal_show() -> None:
    """Ask the running copy to surface its window, then exit ourselves."""
    try:
        k = ctypes.windll.kernel32
        k.OpenEventW.restype = wintypes.HANDLE
        h = k.OpenEventW(0x0002, False, _EVENT)      # EVENT_MODIFY_STATE
        if h:
            k.SetEvent(h)
            k.CloseHandle(h)
    except OSError:
        pass


def make_show_event():
    """The owner creates the event and polls it (see app.py)."""
    try:
        k = ctypes.windll.kernel32
        k.CreateEventW.restype = wintypes.HANDLE
        return k.CreateEventW(None, False, False, _EVENT)
    except OSError:
        return None


def consume_show(handle) -> bool:
    """Non-blocking: True once when another launch asked us to show."""
    if not handle:
        return False
    try:
        return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0
    except OSError:
        return False
