# -*- coding: utf-8 -*-
r"""got_dbg.py — catch the Ghost of Tsushima glyph TESSELLATOR by PAGE_GUARD-ing the
tail-kind2 (FontVerts) page in the running game and recording the RIPs that read it.

DebugActiveProcess (same-user/same-integrity, no admin) + DebugSetProcessKillOnExit(False)
so a debugger exit does NOT kill the game. Arm PAGE_GUARD on the tail page; each read raises
a first-chance STATUS_GUARD_PAGE_VIOLATION whose ExceptionAddress = the accessing instruction
(the vertex fetch). Collect distinct RIPs + accessed offsets, then detach cleanly.

    python got_dbg.py <pid> <tail_va_hex> [seconds]
Prints: {rip: [accessed tail offsets]} — feed the RIPs to capstone (disasm the exec dump).
"""
import sys, ctypes, ctypes.wintypes as wt, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
GUARD = 0x100            # PAGE_GUARD
PAGE_RW = 0x04
STATUS_GUARD_PAGE = 0x80000001
STATUS_SINGLE_STEP = 0x80000004
PAGE = 0x1000


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [("ExceptionCode", wt.DWORD), ("ExceptionFlags", wt.DWORD),
                ("ExceptionRecord", ctypes.c_void_p), ("ExceptionAddress", ctypes.c_void_p),
                ("NumberParameters", wt.DWORD), ("_pad", wt.DWORD),
                ("ExceptionInformation", ctypes.c_ulonglong * 15)]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("ExceptionRecord", EXCEPTION_RECORD), ("dwFirstChance", wt.DWORD)]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [("dwDebugEventCode", wt.DWORD), ("dwProcessId", wt.DWORD),
                ("dwThreadId", wt.DWORD), ("_pad", wt.DWORD),
                ("u", EXCEPTION_DEBUG_INFO), ("_slack", ctypes.c_byte * 64)]


def main():
    pid = int(sys.argv[1])
    tail_va = int(sys.argv[2], 16)
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 25.0
    page = tail_va & ~(PAGE - 1)

    hproc = k32.OpenProcess(0x1F0FFF, False, pid)   # PROCESS_ALL_ACCESS
    if not hproc:
        print(f"OpenProcess failed {ctypes.get_last_error()}"); return 2
    if not k32.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed {ctypes.get_last_error()}"); return 3
    k32.DebugSetProcessKillOnExit(False)

    def arm(pg):
        old = wt.DWORD(0)
        k32.VirtualProtectEx(hproc, ctypes.c_void_p(pg), PAGE, PAGE_RW | GUARD, ctypes.byref(old))

    de = DEBUG_EVENT()
    hits = {}                # rip -> set(offsets)
    armed = False
    t0 = time.time()
    n_events = 0
    # arm ALL tail pages (155 KB ~ 40 pages)
    pages = [page + i * PAGE for i in range(0, 42)]

    def trigger_relayout():
        """Force the UI to re-lay-out text (re-read the outline store) by nudging the window size."""
        try:
            u = ctypes.windll.user32
            u.SetProcessDPIAware()
            hwnd = [0]
            def cb(h, l):
                pd2 = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pd2))
                if pd2.value == pid and u.IsWindowVisible(h):
                    r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
                    if (r.right - r.left) > 500:
                        hwnd[0] = h
                return True
            u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)(cb), 0)
            if hwnd[0]:
                r = wt.RECT(); u.GetWindowRect(hwnd[0], ctypes.byref(r))
                w, h2 = r.right - r.left, r.bottom - r.top
                u.SetWindowPos(hwnd[0], 0, r.left, r.top, w - 120, h2 - 90, 0x0004 | 0x0020)  # NOZORDER|FRAMECHANGED
                u.SetWindowPos(hwnd[0], 0, r.left, r.top, w, h2, 0x0004 | 0x0020)
        except Exception as e:
            print("trigger err", e)
    while time.time() - t0 < secs:
        if k32.WaitForDebugEvent(ctypes.byref(de), 200):
            code = de.dwDebugEventCode
            status = DBG_CONTINUE
            if code == EXCEPTION_DEBUG_EVENT:
                er = de.u.ExceptionRecord
                ec = er.ExceptionCode & 0xffffffff
                if ec == STATUS_GUARD_PAGE:
                    rip = er.ExceptionAddress or 0
                    acc = er.ExceptionInformation[1]
                    if tail_va <= acc < tail_va + 0x26000:
                        hits.setdefault(rip, set()).add(acc - tail_va)
                    # guard auto-cleared by the fault; re-arm that page so we keep catching
                    arm(acc & ~(PAGE - 1))
                    status = DBG_CONTINUE
                elif ec == STATUS_SINGLE_STEP:
                    status = DBG_CONTINUE
                else:
                    status = DBG_EXCEPTION_NOT_HANDLED   # pass real exceptions to the app
            k32.ContinueDebugEvent(de.dwProcessId, de.dwThreadId, status)
            n_events += 1
            if not armed:
                for pg in pages:
                    arm(pg)
                armed = True
                trigger_relayout()
            if len(hits) >= 40:
                break
        else:
            if not armed:
                for pg in pages:
                    arm(pg)
                armed = True
                trigger_relayout()
            elif time.time() - t0 > 4:
                trigger_relayout()   # nudge again to force re-layout while armed

    k32.DebugActiveProcessStop(pid)
    k32.CloseHandle(hproc)
    print(f"events={n_events} distinct RIPs={len(hits)}")
    for rip in sorted(hits):
        offs = sorted(hits[rip])
        print(f"  RIP 0x{rip:012x}  hits={len(offs)} tail-offsets(sample)={offs[:8]}")


if __name__ == "__main__":
    main()
