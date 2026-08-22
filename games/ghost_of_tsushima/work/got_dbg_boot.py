# -*- coding: utf-8 -*-
r"""got_dbg_boot.py — BOOT-TIME capture of the glyph tessellator. Attach the debugger
right after launch (before the menu renders), poll for tail-kind2's VA, arm PAGE_GUARD on
it the moment it loads, and catch the FIRST reads (the initial tessellation, before it is
cached to GPU buffers). This beats the "already-cached" problem of attaching at the menu.

    python got_dbg_boot.py [seconds]     # launches the game itself, attaches, captures
Prints distinct RIPs that read tail-kind2 + the accessed offsets.
"""
import sys, os, ctypes, ctypes.wintypes as wt, time, subprocess, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
EXE = "GhostOfTsushima.exe"
DBG_CONTINUE = 0x00010002
DBG_NOT_HANDLED = 0x80010001
GUARD = 0x100; PAGE_RW = 0x04; PAGE = 0x1000
GUARD_STATUS = 0x80000001
SS_STATUS = 0x80000004
f = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract", "ghost_title.xpps"), "rb").read()
SIG = f[0x97c8d0:0x97c8d0 + 48]

from got_dbg import DEBUG_EVENT  # reuse the struct


def find_tail(hproc, regs_reader):
    # FAST: only READWRITE regions in the font-heap size band (the KCAP is ~10 MB, decompressed
    # into a private RW allocation). This cuts the scan from thousands of regions to a handful,
    # so we arm within ~1 s of the font loading (before the one-time render caches the tessellation).
    for base, size, prot in regs_reader:
        if (prot & 0xff) not in (0x04, 0x40):        # PAGE_READWRITE / EXECUTE_READWRITE
            continue
        if not (4 * 1024 * 1024 <= size <= 96 * 1024 * 1024):
            continue
        d = M.read(hproc, base, size)
        if d:
            o = d.find(SIG)
            if o != -1:
                return base + o
    return None


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    # launch
    env = dict(os.environ, __COMPAT_LAYER="RUNASINVOKER")
    subprocess.Popen([os.path.join(GAME, EXE)], cwd=GAME, env=env, creationflags=0x00000008 | 0x00000200)
    # wait for the pid
    pid = None
    for _ in range(60):
        pid = M.pid()
        if pid:
            break
        time.sleep(0.3)
    if not pid:
        print("no pid"); return 2
    print(f"pid={pid}; attaching early")
    hproc = k32.OpenProcess(0x1F0FFF, False, pid)
    if not k32.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed {ctypes.get_last_error()}"); return 3
    k32.DebugSetProcessKillOnExit(False)

    def arm(pg):
        old = wt.DWORD(0)
        k32.VirtualProtectEx(hproc, ctypes.c_void_p(pg), PAGE, PAGE_RW | GUARD, ctypes.byref(old))

    state = {"tail_va": None, "stop": False}

    # SCANNER THREAD (own process handle): find tail_va ASAP + arm all its pages, re-arm periodically.
    def scanner():
        hp2 = k32.OpenProcess(0x1F0FFF, False, pid)
        tv = None
        npass = 0
        while not state["stop"]:
            if tv is None:
                regs = M.regions(hp2, exec_only=False)
                npass += 1
                tv = find_tail(hp2, regs)
                print(f"[scanner] pass {npass}: {len(regs)} regions, tail {'FOUND' if tv else 'not yet'}, t+{time.time()-t0:.0f}s", flush=True)
                if tv:
                    state["tail_va"] = tv
                    base = tv & ~(PAGE - 1)
                    for i in range(0, 42):
                        arm(base + i * PAGE)
                    print(f"[scanner] tail_va=0x{tv:x} ARMED at t+{time.time()-t0:.0f}s")
            else:
                time.sleep(2.0)   # after found, occasionally re-arm all pages to keep catching
                base = tv & ~(PAGE - 1)
                for i in range(0, 42):
                    arm(base + i * PAGE)
        k32.CloseHandle(hp2)

    de = DEBUG_EVENT()
    hits = {}
    t0 = time.time()
    th = threading.Thread(target=scanner, daemon=True); th.start()
    while time.time() - t0 < secs:
        if k32.WaitForDebugEvent(ctypes.byref(de), 100):
            status = DBG_CONTINUE
            if de.dwDebugEventCode == 1:
                er = de.u.ExceptionRecord
                ec = er.ExceptionCode & 0xffffffff
                if ec == GUARD_STATUS:
                    acc = er.ExceptionInformation[1]
                    tv = state["tail_va"]
                    if tv and tv <= acc < tv + 0x26000:
                        hits.setdefault(er.ExceptionAddress or 0, set()).add(acc - tv)
                    arm(acc & ~(PAGE - 1))
                elif ec == SS_STATUS:
                    pass
                else:
                    status = DBG_NOT_HANDLED
            k32.ContinueDebugEvent(de.dwProcessId, de.dwThreadId, status)
        if len(hits) >= 30:
            break
    state["stop"] = True
    tail_va = state["tail_va"]
    k32.DebugActiveProcessStop(pid)
    k32.CloseHandle(hproc)
    print(f"distinct RIPs={len(hits)} (tail_va {'found' if tail_va else 'NOT found'})")
    for rip in sorted(hits):
        print(f"  RIP 0x{rip:012x} hits={len(hits[rip])} offs={sorted(hits[rip])[:8]}")


if __name__ == "__main__":
    main()
