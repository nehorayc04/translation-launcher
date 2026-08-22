"""Capture ONLY the Winhanced window (never the whole desktop -- a full-screen
grab picks up whatever else the user has open)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import subprocess
import sys
import time
from pathlib import Path

user32 = ctypes.windll.user32


def winhanced_hwnd() -> int | None:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process -Name Winhanced -ErrorAction SilentlyContinue |"
         " Where-Object MainWindowHandle -ne 0 |"
         " Select-Object -First 1).MainWindowHandle"],
        capture_output=True, text=True, timeout=20,
    )
    v = r.stdout.strip()
    return int(v) if v.isdigit() and int(v) else None


def main() -> int:
    out = Path(sys.argv[1])
    hwnd = winhanced_hwnd()
    if not hwnd:
        print("Winhanced has no window")
        return 1

    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(2.0)

    rect = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    box = (rect.left, rect.top, rect.right, rect.bottom)
    if box[2] - box[0] < 100 or box[3] - box[1] < 100:
        print(f"bad window rect {box}")
        return 1

    from PIL import ImageGrab

    img = ImageGrab.grab(bbox=box, all_screens=True)
    img.save(out)
    print(f"saved {out.name} {img.size} luminance={img.convert('L').getextrema()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
