# -*- coding: utf-8 -*-
"""Move GoWR window to top-right + grab it. Usage: python capture.py <out.png> [move]"""
import sys, ctypes, ctypes.wintypes as wt, time, subprocess
from PIL import ImageGrab
user32 = ctypes.windll.user32; user32.SetProcessDPIAware()
SW = user32.GetSystemMetrics(0); SH = user32.GetSystemMetrics(1)
def pids():
    o=subprocess.run(["tasklist","/FI","IMAGENAME eq GoWR.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
    s=set()
    for l in o.splitlines():
        p=[x.strip('"') for x in l.split('","')]
        if len(p)>=2 and p[0].lower().startswith("gowr"):
            try:s.add(int(p[1]))
            except:pass
    return s
def win(ps):
    best=[None,0]
    def cb(h,l):
        if not user32.IsWindowVisible(h):return True
        pd=wt.DWORD();user32.GetWindowThreadProcessId(h,ctypes.byref(pd))
        if pd.value not in ps:return True
        r=wt.RECT();user32.GetWindowRect(h,ctypes.byref(r))
        a=(r.right-r.left)*(r.bottom-r.top)
        if a>best[1]:best[0]=h;best[1]=a
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool,wt.HWND,wt.LPARAM)(cb),0)
    return best[0]
out=sys.argv[1] if len(sys.argv)>1 else "shot.png"
do_move="move" in sys.argv
p=pids()
if not p: print("NOT RUNNING");sys.exit(2)
h=win(p)
if not h: print("no window yet");sys.exit(3)
r=wt.RECT();user32.GetWindowRect(h,ctypes.byref(r))
if r.right-r.left<300: print(f"small {r.right-r.left}x{r.bottom-r.top} loading");sys.exit(4)
W,H=r.right-r.left,r.bottom-r.top
if do_move:
    x=SW-W-8; y=8   # top-right of primary monitor
    user32.SetWindowPos(h,-1,x,y,0,0,0x0001|0x0040)  # SWP_NOSIZE|SWP_SHOWWINDOW, HWND_TOPMOST
    time.sleep(0.6); r=wt.RECT();user32.GetWindowRect(h,ctypes.byref(r))
else:
    user32.SetForegroundWindow(h);time.sleep(0.3);r=wt.RECT();user32.GetWindowRect(h,ctypes.byref(r))
img=ImageGrab.grab(bbox=(r.left,r.top,r.right,r.bottom),all_screens=True)
img.save(out);print(f"captured {out} at ({r.left},{r.top}) {r.right-r.left}x{r.bottom-r.top} screen {SW}x{SH}")
