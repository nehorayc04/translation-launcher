# -*- coding: utf-8 -*-
"""BOOT-TIME tessellator capture, v2 — debugger + SEPARATE scanner process (no GIL contention).
Launch the game, DebugActiveProcess immediately, spawn got_scan_arm.py (arms PAGE_GUARD on
tail-kind2 the instant it loads), and run a MINIMAL debug loop that catches the guard faults =
the tessellator's vertex reads. Prints the RIPs.

    python got_dbg_boot2.py [seconds]
"""
import sys, os, ctypes, ctypes.wintypes as wt, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M
from got_dbg import DEBUG_EVENT

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
EXE = "GhostOfTsushima.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), ".venv", "Scripts", "python.exe")
DBG_CONTINUE = 0x00010002
DBG_NOT_HANDLED = 0x80010001
GUARD_STATUS = 0x80000001
SS_STATUS = 0x80000004
PAGE = 0x1000
TVFILE = os.path.join(HERE, "_tail_va.txt")


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
    if os.path.exists(TVFILE):
        os.remove(TVFILE)
    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    subprocess.Popen([os.path.join(GAME, EXE)], cwd=GAME, env=env, creationflags=0x00000008 | 0x00000200)
    pid = None
    for _ in range(60):
        pid = M.pid()
        if pid:
            break
        time.sleep(0.3)
    if not pid:
        print("no pid"); return 2
    print(f"pid={pid}; attaching + spawning scanner")
    hproc = k32.OpenProcess(0x1F0FFF, False, pid)
    if not k32.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed {ctypes.get_last_error()}"); return 3
    k32.DebugSetProcessKillOnExit(False)
    scanner = subprocess.Popen([PY, os.path.join(HERE, "got_scan_arm.py"), str(pid), TVFILE])

    def arm(pg):
        old = wt.DWORD(0)
        k32.VirtualProtectEx(hproc, ctypes.c_void_p(pg), PAGE, 0x04 | 0x100, ctypes.byref(old))

    de = DEBUG_EVENT()
    hits = {}
    tail_va = None
    t0 = time.time()
    last_tv_check = 0
    while time.time() - t0 < secs:
        if k32.WaitForDebugEvent(ctypes.byref(de), 100):
            status = DBG_CONTINUE
            if de.dwDebugEventCode == 1:
                er = de.u.ExceptionRecord
                ec = er.ExceptionCode & 0xffffffff
                if ec == GUARD_STATUS:
                    acc = er.ExceptionInformation[1]
                    if tail_va and tail_va <= acc < tail_va + 0x26000:
                        hits.setdefault(er.ExceptionAddress or 0, set()).add(acc - tail_va)
                    arm(acc & ~(PAGE - 1))       # re-arm the touched page
                elif ec == SS_STATUS:
                    pass
                else:
                    status = DBG_NOT_HANDLED
            k32.ContinueDebugEvent(de.dwProcessId, de.dwThreadId, status)
        # cheaply pick up tail_va from the scanner's file (no scanning in this process)
        if tail_va is None and time.time() - last_tv_check > 0.3:
            last_tv_check = time.time()
            try:
                tail_va = int(open(TVFILE).read().strip(), 16)
                print(f"[dbg] tail_va={tail_va:#x} (from scanner) t+{time.time()-t0:.1f}s")
            except Exception:
                pass
        if len(hits) >= 30:
            break
    try:
        scanner.terminate()
    except Exception:
        pass
    k32.DebugActiveProcessStop(pid)
    k32.CloseHandle(hproc)
    print(f"distinct RIPs={len(hits)} (tail_va {'found' if tail_va else 'NOT found'})")
    for rip in sorted(hits):
        print(f"  RIP 0x{rip:012x} hits={len(hits[rip])} offs={sorted(hits[rip])[:8]}")


if __name__ == "__main__":
    main()
