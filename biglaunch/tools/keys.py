"""
Drive the Big Launch window from the keyboard so the run/look/fix loop can reach
screens that are several inputs deep (quick menu -> power -> confirmation)
without a human at the pad.

Usage:  python biglaunch/tools/keys.py esc down down enter
        python biglaunch/tools/keys.py --delay 400 esc down enter

Keys: up down left right enter space esc tab f5 f12 a..z 0..9

Why SendInput and not SendKeys: WPF reads real WM_KEYDOWN from the input queue;
SendInput posts exactly that. The window must be FOREGROUND first, which is what
the SetForegroundWindow dance below is for.
"""
import ctypes, sys, time
from ctypes import wintypes

TITLE = "Big Launch"
u = ctypes.windll.user32

VK = {
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "enter": 0x0D, "space": 0x20, "esc": 0x1B, "tab": 0x09,
    "back": 0x08, "f5": 0x74, "f12": 0x7B,
}
# Aliases for the names a caller naturally reaches for. Rejecting "escape"
# because the table says "esc" is a papercut that costs a whole debugging round.
VK["escape"] = VK["esc"]
VK["return"] = VK["enter"]
VK["backspace"] = VK["back"]
for c in "abcdefghijklmnopqrstuvwxyz":
    VK[c] = ord(c.upper())
for d in "0123456789":
    VK[d] = ord(d)


class KBD(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KBD), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def send(vk, up=False):
    i = INPUT(type=1)
    i.ki = KBD(vk, 0, 2 if up else 0, 0, None)
    u.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))


args = sys.argv[1:]
delay = 0.35
if "--delay" in args:
    k = args.index("--delay")
    delay = int(args[k + 1]) / 1000.0
    del args[k:k + 2]

hwnd = u.FindWindowW(None, TITLE)
if not hwnd:
    print("NOT FOUND:", TITLE)
    sys.exit(1)

# Focus-stealing prevention will refuse a bare SetForegroundWindow from a
# background console, so attach to the target's input queue first.
cur = u.GetWindowThreadProcessId(u.GetForegroundWindow(), None)
tgt = u.GetWindowThreadProcessId(hwnd, None)
u.AttachThreadInput(cur, tgt, True)
# 🔴 NOT SW_RESTORE(9) — on a MAXIMIZED window that un-maximizes it, and a 10ft
# shell captured at 1440x753 instead of 1920x1080 looks like a layout bug that
# does not exist. SW_SHOW(5) raises without changing the show-state.
if u.IsIconic(hwnd):
    u.ShowWindow(hwnd, 9)
else:
    u.ShowWindow(hwnd, 5)
u.SetForegroundWindow(hwnd)
u.SetFocus(hwnd)
u.AttachThreadInput(cur, tgt, False)
time.sleep(0.35)

if u.GetForegroundWindow() != hwnd:
    print("WARN: window did not take foreground; keys may go elsewhere")

# 🔴 THIS SCRIPT USED TO LIE. It skipped an unknown key with a warning and then
# printed "sent: <every arg>" unconditionally — so a caller reading the last line
# saw success for a key that was never pressed, and went off debugging the APP for
# a bug that lived here. The summary now lists what actually went out, names what
# did not, and exits non-zero so a script can't silently build on a no-op.
sent, bad = [], []
for name in args:
    vk = VK.get(name.lower())
    if vk is None:
        bad.append(name)
        continue
    send(vk)
    time.sleep(0.03)
    send(vk, up=True)
    time.sleep(delay)
    sent.append(name)

print("sent:", " ".join(sent) if sent else "(nothing)")
if bad:
    print("UNKNOWN KEY:", " ".join(bad), "- nothing was pressed for these")
    sys.exit(2)
