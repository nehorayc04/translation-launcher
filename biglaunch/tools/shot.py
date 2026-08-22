"""
Capture the Big Launch window to a PNG — the instrument for the run/look/fix loop.

Usage:  python biglaunch/tools/shot.py [out.png] [--mirror] [--crop L,T,R,B]

🔴 THE MIRROR TRAP, settled empirically on this window
------------------------------------------------------
The window carries WS_EX_LAYOUTRTL (FlowDirection=RightToLeft), and the old
`C:\\tmp\\cap_window.py` un-mirrors every capture because a plain PrintWindow
renders THROUGH that layout. That is true for the legacy WM_PRINT path — but
with **PW_RENDERFULLCONTENT (2)** on a DWM-composited WPF window the frame comes
back from the redirection surface ALREADY in screen orientation, so un-mirroring
it produces a perfectly mirrored image of a perfectly correct app.

Measured on this exact window: flag detected RTL=True, PrintWindow(2)=1, and the
raw bitmap reads correctly (Latin box-art text left-to-right). So the default
here is NO mirror; `--mirror` is kept only for a window that genuinely needs it.

The lesson generalises: a capture instrument can lie, and a mirrored screenshot
reads exactly like a broken RTL layout. Verify with a KNOWN-LTR string in frame
(a Latin game title) before believing the picture.
"""
import ctypes, sys, statistics
from ctypes import wintypes

TITLE = "Big Launch"
u, g, dwm = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.dwmapi

args = [a for a in sys.argv[1:]]
mirror = "--mirror" in args
args = [a for a in args if not a.startswith("--") or a.startswith("--crop")]
crop = None
for a in list(args):
    if a.startswith("--crop"):
        crop = tuple(int(x) for x in a.split("=", 1)[1].split(","))
        args.remove(a)
out = args[0] if args else r"C:\tmp\bl.png"

hwnd = u.FindWindowW(None, TITLE)
if not hwnd:
    print("NOT FOUND:", TITLE)
    sys.exit(1)


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long)]


r = RECT()
if dwm.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
    u.GetWindowRect(hwnd, ctypes.byref(r))
w, h = r.r - r.l, r.b - r.t

hdc = u.GetWindowDC(hwnd)
mem = g.CreateCompatibleDC(hdc)
# The bitmap MUST come from the WINDOW dc — a fresh memory DC yields a 1-bpp
# monochrome bitmap and every capture is solid black.
bmp = g.CreateCompatibleBitmap(hdc, w, h)
g.SelectObject(mem, bmp)
ok = u.PrintWindow(hwnd, mem, 2)   # PW_RENDERFULLCONTENT — required for WPF/DWM


class BMIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class BMI(ctypes.Structure):
    _fields_ = [("h", BMIH), ("c", ctypes.c_uint32 * 3)]


bi = BMI()
bi.h.biSize = ctypes.sizeof(BMIH)
bi.h.biWidth, bi.h.biHeight = w, -h      # negative = top-down
bi.h.biPlanes, bi.h.biBitCount = 1, 32
buf = ctypes.create_string_buffer(w * h * 4)
g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)

from PIL import Image, ImageOps
img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
if mirror:
    img = ImageOps.mirror(img)
if crop:
    img = img.crop(crop)
img.save(out)

px = list(img.convert("L").getdata())
print(f"saved {out} {img.size} printwindow={ok} mean={statistics.mean(px):.1f}")

g.DeleteObject(bmp)
g.DeleteDC(mem)
u.ReleaseDC(hwnd, hdc)
