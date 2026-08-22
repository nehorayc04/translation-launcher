#!/usr/bin/env python3
"""Grab the Assassin's Creed Shadows window to a PNG so the menu can be
inspected (Stage-0 Arabic-slot test). Read-only; captures screen pixels only.

Finds the ACShadows top-level window via Win32 (ctypes), grabs its rect over the
virtual desktop (multi-monitor safe), and reports a luminance check so an
all-black exclusive-fullscreen grab is flagged (GDI can't read a DXGI exclusive
surface -> use borderless windowed).

    python acs_capture.py [out.png]
"""
import sys
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

OUT = sys.argv[1] if len(sys.argv) > 1 else r"c:\tmp\acs_menu.png"

titles = []
hwnds = []

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _enum(hwnd, _):
    if not user32.IsWindowVisible(hwnd):
        return True
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    t = buf.value
    if "assassin" in t.lower() or "shadows" in t.lower() or "acshadows" in t.lower():
        titles.append(t)
        hwnds.append(hwnd)
    return True


user32.EnumWindows(EnumWindowsProc(_enum), 0)

if not hwnds:
    print("NO ACShadows window found yet (still booting / splash, or no titled window).")
    sys.exit(3)

hwnd = hwnds[0]
print(f"window: {titles[0]!r}  hwnd={hwnd}")

rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
bbox = (rect.left, rect.top, rect.right, rect.bottom)
print(f"rect: {bbox}")

try:
    from PIL import ImageGrab, ImageStat
    img = ImageGrab.grab(bbox=bbox, all_screens=True)
    img.save(OUT)
    gray = img.convert("L")
    st = ImageStat.Stat(gray)
    mn, mx = gray.getextrema()
    print(f"saved {OUT}  size={img.size}  mean_lum={st.mean[0]:.1f}  extrema=({mn},{mx})")
    if mx == 0:
        print("  ALL-BLACK -> exclusive fullscreen (GDI can't capture). Switch to borderless windowed.")
        sys.exit(4)
except Exception as e:
    print(f"capture failed: {e}")
    sys.exit(5)
