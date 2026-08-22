import sys, time, subprocess, os, ctypes
from PIL import ImageGrab
import numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GAME = r"D:/Games/Assassin's Creed II"; EXE = GAME + "/AssassinsCreedIIGame.exe"
OUT = r"c:/tmp/ac2_caps"; os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    try: os.remove(os.path.join(OUT, f))
    except Exception: pass
u32 = ctypes.windll.user32

def win_for_pid(pid):
    """match the window by PID -- NOT by title: the IDE's title also contains the game name."""
    res = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, l):
        p = ctypes.c_ulong(); u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h): res.append(h)
        return True
    u32.EnumWindows(cb, 0)
    return res[0] if res else None

os.environ["__COMPAT_LAYER"] = "RUNASINVOKER"
proc = subprocess.Popen([EXE], cwd=GAME, creationflags=0x00000008)
print("launched pid", proc.pid, flush=True)
for k in range(30):
    time.sleep(5)
    h = win_for_pid(proc.pid)
    if h:
        u32.ShowWindow(h, 9); u32.SetForegroundWindow(h)
    try:
        img = ImageGrab.grab(all_screens=True)
    except OSError:
        continue
    m = np.asarray(img.convert("L")).mean()
    p = os.path.join(OUT, f"c_{k:02d}_m{m:.0f}.png"); img.save(p)
    print(f"  {k}: mean={m:.1f} hwnd={h}", flush=True)   # keep ALL frames; inspect the last stable one
print("DONE", flush=True)
