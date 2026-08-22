import sys, ctypes, ctypes.wintypes as wt, time, subprocess
user32=ctypes.windll.user32; user32.SetProcessDPIAware()
def pids():
    o=subprocess.run(["tasklist","/FI","IMAGENAME eq GoWR.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
    r=set()
    for l in o.splitlines():
        p=[x.strip('"') for x in l.split('","')]
        if len(p)>=2 and p[0].lower().startswith('gowr'):
            try:r.add(int(p[1]))
            except:pass
    return r
def win(ps):
    b=[None,0]
    def cb(h,l):
        if not user32.IsWindowVisible(h):return True
        d=wt.DWORD();user32.GetWindowThreadProcessId(h,ctypes.byref(d))
        if d.value not in ps:return True
        r=wt.RECT();user32.GetWindowRect(h,ctypes.byref(r));a=(r.right-r.left)*(r.bottom-r.top)
        if a>b[1]:b[0]=h;b[1]=(a);b.append(r)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool,wt.HWND,wt.LPARAM)(cb),0);return b[0]
h=win(pids())
r=wt.RECT();user32.GetWindowRect(h,ctypes.byref(r))
# args = relative x,y fractions (0..1) within the CLIENT area
fx,fy=float(sys.argv[1]),float(sys.argv[2])
x=int(r.left+(r.right-r.left)*fx); y=int(r.top+(r.bottom-r.top)*fy)
user32.SetForegroundWindow(h); time.sleep(0.4)
user32.SetCursorPos(x,y); time.sleep(0.25)
user32.mouse_event(0x0002,0,0,0,0); time.sleep(0.05); user32.mouse_event(0x0004,0,0,0,0)  # L down/up
print(f"clicked ({x},{y}) win=({r.left},{r.top},{r.right},{r.bottom})")
