"""Launch Winhanced, wait for its window, screenshot it, then close it.

Finds the window by PID (never by title -- an IDE window whose title contains
the app name would be grabbed instead) and captures the window rect off the
virtual desktop so a second monitor works too.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import subprocess
import sys
import time
from pathlib import Path

EXE = Path(r"C:\Program Files\Winhanced\Winhanced.exe")
user32 = ctypes.windll.user32


def _windows_of_pid(pid: int) -> list[int]:
    out: list[int] = []
    CB = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

    def cb(hwnd, _):
        p = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = w.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if (r.right - r.left) > 400 and (r.bottom - r.top) > 300:
                out.append(hwnd)
        return True

    user32.EnumWindows(CB(cb), 0)
    return out


def grab(hwnd: int, path: Path) -> None:
    from PIL import ImageGrab

    r = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab(
        bbox=(r.left, r.top, r.right, r.bottom), all_screens=True
    )
    img.save(path)
    ex = img.convert("L").getextrema()
    print(f"  saved {path}  {img.size}  luminance {ex}")
    if ex[1] == 0:
        print("  !! all-black: GDI cannot read this surface; needs dxcam")


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "shot.png")
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0

    proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent))
    print(f"launched pid={proc.pid}")

    hwnd = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(1.0)
        # the launcher may hand off to a new pid, so scan all Winhanced procs
        pids = [proc.pid]
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Process -Name Winhanced -ErrorAction SilentlyContinue).Id"],
                capture_output=True, text=True, timeout=15,
            )
            pids += [int(x) for x in r.stdout.split() if x.strip().isdigit()]
        except Exception:  # noqa: BLE001
            pass
        for pid in dict.fromkeys(pids):
            ws = _windows_of_pid(pid)
            if ws:
                hwnd = ws[0]
                break
        if hwnd:
            break

    if not hwnd:
        print("no window appeared")
        return 1

    print(f"window found after {time.time()-t0:.1f}s; settling…")
    time.sleep(12)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.5)
    grab(hwnd, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
