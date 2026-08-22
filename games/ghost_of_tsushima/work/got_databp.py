# -*- coding: utf-8 -*-
r"""got_databp.py — HW DATA read/write watchpoint on the runtime font cmap/table, to catch the
tessellator's RIP (a real code anchor into the font pipeline that font STRINGS never gave).

Sets DR0 as a read/write watchpoint (R/W=11, LEN=4) on a data address; on hit, records the
DISTINCT accessing RIPs + a small register snapshot. Menu text renders every frame, so a
watchpoint on the Latin glyph-table fires immediately.

    python got_databp.py <watch_va_hex> [max_distinct=12] [seconds=60]
Run with the repo .venv python while the game is at the menu.
"""
import sys, os, ctypes, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M
from got_codebp import (CONTEXT, DEBUG_EVENT, aligned_ctx, all_thread_ids, CTX_FLAGS,
                        DBG_CONTINUE, DBG_EXCEPTION_NOT_HANDLED, EXCEPTION_DEBUG_EVENT,
                        CREATE_THREAD_DEBUG_EVENT, STATUS_SINGLE_STEP, STATUS_BREAKPOINT,
                        STATUS_WX86_SINGLE_STEP, THREAD_ALL, k32)


def set_watch(tid, addr, clear=False):
    h = k32.OpenThread(THREAD_ALL, False, tid)
    if not h:
        return
    k32.SuspendThread(h)
    raw, ctx = aligned_ctx()
    if k32.GetThreadContext(h, ctypes.byref(ctx)):
        if clear:
            ctx.Dr0 = 0; ctx.Dr7 &= ~0x1
        else:
            ctx.Dr0 = addr
            # L0 enable(bit0) | R/W0=11 read|write (bits16-17) | LEN0=11 4-byte (bits18-19)
            ctx.Dr7 = (ctx.Dr7 & ~0x000F0000) | 0x000D0001
            ctx.Dr6 = 0
        ctx.ContextFlags = CTX_FLAGS
        k32.SetThreadContext(h, ctypes.byref(ctx))
    k32.ResumeThread(h); k32.CloseHandle(h)


def main():
    if len(sys.argv) < 2:
        print("usage: got_databp.py <watch_va_hex> [max_distinct] [seconds]"); return 2
    watch = int(sys.argv[1], 16)
    maxd = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
    pid = M.pid()
    if not pid:
        print("game not running"); return 3
    hp = M.open_proc(pid)
    regs = M.regions(hp, exec_only=False)
    def is_exec(a):
        return any(b <= a < b + s and (p & 0xff) in M.PAGE_EXEC for b, s, p in regs)

    if not k32.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed {ctypes.get_last_error()}"); return 4
    k32.DebugSetProcessKillOnExit(False)
    for tid in all_thread_ids(pid):
        set_watch(tid, watch)
    print(f"watchpoint armed on 0x{watch:012x} (all threads). capturing accessing RIPs...", flush=True)

    de = DEBUG_EVENT()
    rips = {}     # rip -> hit count
    t0 = time.time()
    while time.time() - t0 < secs and len(rips) < maxd:
        if not k32.WaitForDebugEvent(ctypes.byref(de), 200):
            continue
        status = DBG_CONTINUE
        if de.dwDebugEventCode == CREATE_THREAD_DEBUG_EVENT:
            set_watch(de.dwThreadId, watch)
        elif de.dwDebugEventCode == EXCEPTION_DEBUG_EVENT:
            er = de.u.Exception.ExceptionRecord
            ec = er.ExceptionCode & 0xffffffff
            if ec in (STATUS_SINGLE_STEP, STATUS_WX86_SINGLE_STEP):
                th = k32.OpenThread(THREAD_ALL, False, de.dwThreadId)
                raw, ctx = aligned_ctx()
                k32.GetThreadContext(th, ctypes.byref(ctx))
                if ctx.Dr6 & 0x1:                     # our DR0 watchpoint
                    rip = ctx.Rip
                    if rip not in rips:
                        exe = is_exec(rip)
                        print(f"  RIP 0x{rip:012x} exec={exe}  rax=0x{ctx.Rax:x} rcx=0x{ctx.Rcx:x} "
                              f"rdx=0x{ctx.Rdx:x} rsi=0x{ctx.Rsi:x} rdi=0x{ctx.Rdi:x} r8=0x{ctx.R8:x}", flush=True)
                    rips[rip] = rips.get(rip, 0) + 1
                    ctx.Dr6 = 0; ctx.ContextFlags = CTX_FLAGS
                    k32.SetThreadContext(th, ctypes.byref(ctx))
                k32.CloseHandle(th)
            elif ec == STATUS_BREAKPOINT:
                pass
            else:
                status = DBG_EXCEPTION_NOT_HANDLED
        k32.ContinueDebugEvent(de.dwProcessId, de.dwThreadId, status)

    for tid in all_thread_ids(pid):
        set_watch(tid, watch, clear=True)
    k32.DebugActiveProcessStop(pid)
    k32.CloseHandle(hp)
    print(f"\n=== {len(rips)} distinct accessing RIPs (count) ===")
    for rip, c in sorted(rips.items(), key=lambda x: -x[1]):
        print(f"  0x{rip:012x}  hits={c}")


if __name__ == "__main__":
    sys.exit(main() or 0)
