"""Launch SkyrimSELauncher.exe, screenshot the menu AND the Options dialog, close.

The launcher is a plain GDI/Win32 window, so ImageGrab works (unlike the DX11 game,
which needs dxcam). The Options dialog is where the RT_STRING surface is visible, so
the menu row is located by INK (not by hardcoded coordinates) and clicked.

usage: python launcher_check.py [out_prefix]
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import ImageGrab

GAME = Path(r"D:\Games\TES - Skyrim - Anniversary Edition")
EXE = GAME / "SkyrimSELauncher.exe"
u32 = ctypes.windll.user32


def pids(name="SkyrimSELauncher.exe") -> list[int]:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True).stdout
    return [int(l.split('","')[1].strip('"')) for l in out.splitlines() if name in l]


def kill() -> None:
    for n in ("SkyrimSELauncher.exe", "SkyrimSE.exe"):
        for p in pids(n):
            subprocess.run(["taskkill", "/F", "/PID", str(p)], capture_output=True)


def top_window(pid: int):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not u32.IsWindowVisible(hwnd):
            return True
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            r = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right - r.left > 300 and r.bottom - r.top > 200:
                found.append((hwnd, (r.left, r.top, r.right, r.bottom)))
        return True

    u32.EnumWindows(cb, 0)
    found.sort(key=lambda t: -(t[1][2] - t[1][0]) * (t[1][3] - t[1][1]))
    return found[0] if found else None


def grab(rect):
    return ImageGrab.grab(bbox=rect, all_screens=True).convert("RGB")


def menu_rows(img, rect):
    """Find the bright right-hand menu rows by ink, so no coordinate is hardcoded."""
    a = np.asarray(img.convert("L")).astype(int)
    h, w = a.shape
    # the menu column, TOP HALF only -- the Bethesda logo lives in the same column
    # near the bottom and otherwise gets picked as a "menu row" (it did).
    band = a[:int(h * 0.6), int(w * 0.72):]
    # UNHOVERED menu items are the DIM state (measured ink peak 85), so a >90
    # threshold finds nothing at all -- only the hovered item and the logo.
    # UNHOVERED menu items are the DIM state (measured ink peak 85), so a >90
    # threshold finds nothing at all -- only the hovered item and the logo. And
    # Hebrew strokes are thin, so a per-row run breaks into fragments unless small
    # vertical gaps are BRIDGED before grouping.
    on = (band > 30).sum(axis=1) > 1
    gap = 0
    merged = on.copy()
    for y in range(len(on)):
        if on[y]:
            gap = 0
        else:
            gap += 1
            if gap <= 8:
                merged[y] = True
    rows, run = [], None
    for y, v in enumerate(list(merged) + [False]):
        if v and run is None:
            run = y
        elif not v and run is not None:
            if 10 <= y - run <= 60:                 # a menu row, not the logo block
                rows.append((run, y))
            run = None
    return rows


def click(rect, x, y):
    u32.SetCursorPos(rect[0] + x, rect[1] + y)
    time.sleep(0.25)
    u32.mouse_event(0x0002, 0, 0, 0, 0)             # LEFTDOWN
    time.sleep(0.06)
    u32.mouse_event(0x0004, 0, 0, 0, 0)             # LEFTUP


def main() -> int:
    prefix = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("_launcher")
    kill()
    time.sleep(0.8)
    # the launcher's manifest demands admin -> a plain Popen dies with WinError 740.
    # RUNASINVOKER makes the AppCompat shim ignore the manifest: no UAC, no elevation.
    import os
    subprocess.Popen([str(EXE)], cwd=str(GAME),
                     env=dict(os.environ, __COMPAT_LAYER="RUNASINVOKER"),
                     creationflags=subprocess.DETACHED_PROCESS)
    win = None
    for _ in range(40):
        time.sleep(1)
        ps = pids()
        if ps:
            win = top_window(ps[-1])
            if win:
                break
    if not win:
        print("launcher window never appeared")
        kill()
        return 1
    hwnd, rect = win
    u32.SetForegroundWindow(hwnd)
    time.sleep(1.5)
    img = grab(rect)
    p1 = prefix.with_name(prefix.name + "_menu.png")
    img.save(p1)
    print(f"-> {p1}  {img.size}  rect={rect}")

    rows = menu_rows(img, rect)
    print(f"menu rows found: {rows}")
    if len(rows) >= 2:
        y0, y1 = rows[1]                            # 2nd item = OPTIONS
        cx = int(img.size[0] * 0.90)
        click(rect, cx, (y0 + y1) // 2)
        time.sleep(3.0)
        # ImageGrab captures a SCREEN region, so the dialog must be FOREGROUND or we
        # photograph whatever window happens to sit at those coordinates.
        fg = u32.GetForegroundWindow()
        r = wintypes.RECT()
        u32.GetWindowRect(fg, ctypes.byref(r))
        r2 = (r.left, r.top, r.right, r.bottom)
        same = r2 == rect
        print(f"foreground after click: rect={r2} {'(dialog did NOT open)' if same else ''}")
        if not same and r2[2] - r2[0] > 100:
            u32.SetForegroundWindow(fg)
            time.sleep(0.6)
            img2 = grab(r2)
            p2 = prefix.with_name(prefix.name + "_options.png")
            img2.save(p2)
            print(f"-> {p2}  {img2.size}")
    time.sleep(0.5)
    kill()
    print("closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
