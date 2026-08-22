import sys, time, subprocess, os
from PIL import ImageGrab
import numpy as np
import ctypes
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GAME = r"D:/Games/Assassin's Creed II"
EXE = GAME + "/AssassinsCreedIIGame.exe"
OUT = r"c:/tmp/ac2_caps"; os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    try: os.remove(os.path.join(OUT, f))
    except: pass

u32 = ctypes.windll.user32
def find_ac2():
    res = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, l):
        n = u32.GetWindowTextLengthW(h)
        if n:
            b = ctypes.create_unicode_buffer(n+1); u32.GetWindowTextW(h, b, n+1)
            if "Assassin" in b.value: res.append(h)
        return True
    u32.EnumWindows(cb, 0)
    return res[0] if res else None

print("launching...", flush=True)
subprocess.Popen([EXE], cwd=GAME, creationflags=0x00000008)
time.sleep(85)
best = None
for k in range(12):
    h = find_ac2()
    if h:
        u32.ShowWindow(h, 9); u32.SetForegroundWindow(h)
    time.sleep(3)
    img = ImageGrab.grab(all_screens=True)
    a = np.asarray(img.convert("L")); m = a.mean()
    p = os.path.join(OUT, f"c_{k:02d}_m{m:.0f}.png"); img.save(p)
    print(f"  {k}: mean={m:.1f} hwnd={h}", flush=True)
    if m > 150: best = p
print("BEST bright frame:", best, flush=True)
