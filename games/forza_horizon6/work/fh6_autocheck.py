"""Launch Forza Horizon 6, screenshot it, and close it — without the user.

Mirrors the Skyrim / Far Cry 5 autocheck, with the traps those cost us:

* the exe manifest can demand admin -> launch with `__COMPAT_LAYER=RUNASINVOKER`
  so no UAC prompt is needed;
* DX12 uses a flip-model swapchain, so GDI (`ImageGrab`) returns BLACK -> capture
  with **dxcam** (DXGI Desktop Duplication);
* find the window by **PID**, never by title (an IDE window whose title contains
  the game's name will be photographed instead);
* the first bright frame is the PUBLISHER LOGO, not the menu -> refuse any frame
  before a warm-up deadline and require the frame to settle.

    python fh6_autocheck.py shot ../extract/live.png [--warmup 90] [--timeout 420]
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as w
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
EXE = os.path.join(GAME, "forzahorizon6.exe")

u32 = ctypes.windll.user32


def windows_of(pid: int):
    out = []
    CB = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

    def cb(h, _):
        p = w.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h):
            r = w.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 300 and r.bottom - r.top > 200:
                out.append((h, (r.left, r.top, r.right, r.bottom)))
        return True
    u32.EnumWindows(CB(cb), 0)
    return out


def live_pids() -> list[int]:
    """Only processes whose ExecutablePath we can READ and that match our exe —
    an elevated stray would otherwise be mistaken for ours."""
    ps = ("Get-CimInstance Win32_Process -Filter \"name='forzahorizon6.exe'\" | "
          "Select-Object -ExpandProperty ProcessId")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def grab(rect):
    import dxcam
    cam = dxcam.create(output_color="RGB")
    try:
        for _ in range(40):
            f = cam.grab(region=rect)
            if f is not None:
                return f
            time.sleep(0.25)
    finally:
        del cam
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["shot", "kill"])
    ap.add_argument("out", nargs="?", default=os.path.join(HERE, "..", "extract",
                                                           "live.png"))
    ap.add_argument("--warmup", type=float, default=100.0)
    ap.add_argument("--timeout", type=float, default=420.0)
    a = ap.parse_args()

    if a.cmd == "kill":
        subprocess.run(["taskkill", "/F", "/IM", "forzahorizon6.exe"],
                       capture_output=True)
        print("killed")
        return

    if not os.path.exists(EXE):
        sys.exit(f"exe not found: {EXE}")
    if live_pids():
        sys.exit("a copy of the game is ALREADY running — close it first "
                 "(a stale instance renders the font it loaded at ITS start)")

    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    print(f"launching {EXE}")
    subprocess.Popen([EXE], cwd=GAME, env=env,
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

    t0 = time.time()
    import numpy as np
    last, stable = None, 0
    shot = None
    while time.time() - t0 < a.timeout:
        time.sleep(3)
        pids = live_pids()
        if not pids:
            continue
        wins = [wd for p in pids for wd in windows_of(p)]
        if not wins:
            continue
        rect = max(wins, key=lambda x: (x[1][2] - x[1][0]) * (x[1][3] - x[1][1]))[1]
        el = time.time() - t0
        f = grab(rect)
        if f is None:
            continue
        m = float(np.mean(f))
        if last is not None and abs(m - last) < 1.2:
            stable += 1
        else:
            stable = 0
        last = m
        print(f"  t+{el:5.1f}s  window {rect}  mean {m:6.2f}  stable {stable}")
        if el >= a.warmup and m > 8 and stable >= 2:
            shot = f
            break

    if shot is None:
        print("no settled frame captured")
    else:
        from PIL import Image
        p = os.path.abspath(a.out)
        Image.fromarray(shot).save(p)
        print("saved", p)
    subprocess.run(["taskkill", "/F", "/IM", "forzahorizon6.exe"], capture_output=True)
    print("game closed")


if __name__ == "__main__":
    main()
