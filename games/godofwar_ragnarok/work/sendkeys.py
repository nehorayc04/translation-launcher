# -*- coding: utf-8 -*-
"""Focus GoWR + send a key sequence. Usage: python sendkeys.py down down enter"""
import sys, ctypes, ctypes.wintypes as wt, time, subprocess
user32=ctypes.windll.user32; user32.SetProcessDPIAware()
PUL=ctypes.POINTER(ctypes.c_ulong)
class KBD(ctypes.Structure):
    _fields_=[("wVk",ctypes.c_ushort),("wScan",ctypes.c_ushort),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",PUL)]
class INP(ctypes.Structure):
    class _U(ctypes.Union): _fields_=[("ki",KBD)]
    _anonymous_=("u",); _fields_=[("type",ctypes.c_ulong),("u",_U)]
SC={'down':(0x50,True),'up':(0x48,True),'left':(0x4B,True),'right':(0x4D,True),'enter':(0x1C,False),'esc':(0x01,False),'space':(0x39,False),'tab':(0x0F,False)}
def send(scan,ext,down):
    fl=0x08|(0x01 if ext else 0)|(0 if down else 0x02)
    i=INP(type=1); i.ki=KBD(0,scan,fl,0,None); user32.SendInput(1,ctypes.byref(i),ctypes.sizeof(i))
def tap(name):
    s,e=SC[name]; send(s,e,True); time.sleep(0.04); send(s,e,False)
def pids():
    o=subprocess.run(["tasklist","/FI","IMAGENAME eq GoWR.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
    r=set()
    for l in o.splitlines():
        p=[x.strip('\"') for x in l.split('\",\"')]
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
        if a>b[1]:b[0]=h;b[1]=a
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool,wt.HWND,wt.LPARAM)(cb),0);return b[0]
h=win(pids())
if not h: print("no window");sys.exit(1)
user32.ShowWindow(h,9); user32.SetForegroundWindow(h); time.sleep(0.6)
for a in sys.argv[1:]:
    tap(a); time.sleep(0.35)
print("sent:", " ".join(sys.argv[1:]))
