# -*- coding: utf-8 -*-
r"""got_codebp.py — HARDWARE execute breakpoint on the font tessellator, dump the data flow.

Sets DR0 (execute, stealthier than INT3 = no code-byte change, no VMProtect code-checksum trip)
at the tessellator anchor on EVERY thread (existing + newly created). When it fires we read the
full x64 CONTEXT and, for every register that points into committed memory, dump 96 bytes there
+ the stack top. Goal: catch the packed FONT-DATA source pointer and the freshly-written VERTEX
output pointer at the moment of decode → recover the on-disk coord codec.

    python got_codebp.py <anchor_va_hex> [max_hits] [seconds]
The game must be at the MENU. AFTER this prints "ARMED", trigger a re-tessellation in-game
(Settings -> change Text Language, or open a fresh menu). Run with the repo .venv python.
"""
import sys, os, ctypes, ctypes.wintypes as wt, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001
EXCEPTION_DEBUG_EVENT = 1
CREATE_THREAD_DEBUG_EVENT = 2
EXIT_THREAD_DEBUG_EVENT = 5
STATUS_SINGLE_STEP = 0x80000004
STATUS_BREAKPOINT = 0x80000003
STATUS_WX86_SINGLE_STEP = 0x4000001E
TH32CS_SNAPTHREAD = 0x00000004
THREAD_ALL = 0x1FFFFF
CTX_FLAGS = 0x00100000 | 0x1 | 0x2 | 0x10   # AMD64 | CONTROL | INTEGER | DEBUG_REGISTERS


class M128A(ctypes.Structure):
    _fields_ = [("Low", ctypes.c_ulonglong), ("High", ctypes.c_longlong)]


class CONTEXT(ctypes.Structure):
    _pack_ = 16
    _fields_ = [
        ("P1Home", ctypes.c_ulonglong), ("P2Home", ctypes.c_ulonglong),
        ("P3Home", ctypes.c_ulonglong), ("P4Home", ctypes.c_ulonglong),
        ("P5Home", ctypes.c_ulonglong), ("P6Home", ctypes.c_ulonglong),
        ("ContextFlags", wt.DWORD), ("MxCsr", wt.DWORD),
        ("SegCs", wt.WORD), ("SegDs", wt.WORD), ("SegEs", wt.WORD),
        ("SegFs", wt.WORD), ("SegGs", wt.WORD), ("SegSs", wt.WORD),
        ("EFlags", wt.DWORD),
        ("Dr0", ctypes.c_ulonglong), ("Dr1", ctypes.c_ulonglong),
        ("Dr2", ctypes.c_ulonglong), ("Dr3", ctypes.c_ulonglong),
        ("Dr6", ctypes.c_ulonglong), ("Dr7", ctypes.c_ulonglong),
        ("Rax", ctypes.c_ulonglong), ("Rcx", ctypes.c_ulonglong),
        ("Rdx", ctypes.c_ulonglong), ("Rbx", ctypes.c_ulonglong),
        ("Rsp", ctypes.c_ulonglong), ("Rbp", ctypes.c_ulonglong),
        ("Rsi", ctypes.c_ulonglong), ("Rdi", ctypes.c_ulonglong),
        ("R8", ctypes.c_ulonglong), ("R9", ctypes.c_ulonglong),
        ("R10", ctypes.c_ulonglong), ("R11", ctypes.c_ulonglong),
        ("R12", ctypes.c_ulonglong), ("R13", ctypes.c_ulonglong),
        ("R14", ctypes.c_ulonglong), ("R15", ctypes.c_ulonglong),
        ("Rip", ctypes.c_ulonglong),
        ("FltSave", ctypes.c_byte * 512),
        ("Vector", M128A * 26),
        ("VectorControl", ctypes.c_ulonglong),
        ("DebugControl", ctypes.c_ulonglong),
        ("LastBranchToRip", ctypes.c_ulonglong),
        ("LastBranchFromRip", ctypes.c_ulonglong),
        ("LastExceptionToRip", ctypes.c_ulonglong),
        ("LastExceptionFromRip", ctypes.c_ulonglong),
    ]


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [("ExceptionCode", wt.DWORD), ("ExceptionFlags", wt.DWORD),
                ("ExceptionRecord", ctypes.c_void_p), ("ExceptionAddress", ctypes.c_void_p),
                ("NumberParameters", wt.DWORD),
                ("ExceptionInformation", ctypes.c_ulonglong * 15)]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("ExceptionRecord", EXCEPTION_RECORD), ("dwFirstChance", wt.DWORD)]


class CREATE_THREAD_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("hThread", wt.HANDLE), ("lpThreadLocalBase", ctypes.c_void_p),
                ("lpStartAddress", ctypes.c_void_p)]


class DBG_U(ctypes.Union):
    _fields_ = [("Exception", EXCEPTION_DEBUG_INFO),
                ("CreateThread", CREATE_THREAD_DEBUG_INFO),
                ("_pad", ctypes.c_byte * 160)]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [("dwDebugEventCode", wt.DWORD), ("dwProcessId", wt.DWORD),
                ("dwThreadId", wt.DWORD), ("u", DBG_U)]


def aligned_ctx():
    raw = (ctypes.c_byte * (ctypes.sizeof(CONTEXT) + 16))()
    ad = (ctypes.addressof(raw) + 15) & ~15
    ctx = ctypes.cast(ad, ctypes.POINTER(CONTEXT)).contents
    ctx.ContextFlags = CTX_FLAGS
    return raw, ctx   # keep raw alive


def set_hwbp_on_thread(tid, anchor):
    h = k32.OpenThread(THREAD_ALL, False, tid)
    if not h:
        return False
    k32.SuspendThread(h)
    raw, ctx = aligned_ctx()
    ok = k32.GetThreadContext(h, ctypes.byref(ctx))
    if ok:
        ctx.Dr0 = anchor
        ctx.Dr7 = (ctx.Dr7 & ~0x000F0003) | 0x00000001   # L0 enable, R/W0=00 exec, LEN0=00
        ctx.Dr6 = 0
        ctx.ContextFlags = CTX_FLAGS
        ok = k32.SetThreadContext(h, ctypes.byref(ctx))
    k32.ResumeThread(h)
    k32.CloseHandle(h)
    return bool(ok)


def all_thread_ids(pid):
    class TE(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                    ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", ctypes.c_long),
                    ("tpDeltaPri", ctypes.c_long), ("dwFlags", wt.DWORD)]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = TE(); te.dwSize = ctypes.sizeof(TE)
    out = []
    if k32.Thread32First(snap, ctypes.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                out.append(te.th32ThreadID)
            if not k32.Thread32Next(snap, ctypes.byref(te)):
                break
    k32.CloseHandle(snap)
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: got_codebp.py <anchor_va_hex> [max_hits=8] [seconds=180]"); return 2
    anchor = int(sys.argv[1], 16)
    max_hits = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 180.0

    pid = M.pid()
    if not pid:
        print("game not running"); return 3
    hp = M.open_proc(pid)
    regs = M.regions(hp, exec_only=False)
    def region_of(a):
        for b, s, p in regs:
            if b <= a < b + s:
                return b, s, p
        return None

    if not k32.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed err={ctypes.get_last_error()} (already debugged?)"); return 4
    k32.DebugSetProcessKillOnExit(False)

    for tid in all_thread_ids(pid):
        set_hwbp_on_thread(tid, anchor)
    print(f"pid={pid} anchor=0x{anchor:012x}  HW-BP armed on all threads.")
    print(">>> ARMED — NOW in-game: open Settings and CHANGE the Text Language (forces a font re-tessellation). <<<", flush=True)

    de = DEBUG_EVENT()
    hits = 0
    t0 = time.time()
    while time.time() - t0 < secs and hits < max_hits:
        if not k32.WaitForDebugEvent(ctypes.byref(de), 200):
            continue
        status = DBG_CONTINUE
        code = de.dwDebugEventCode
        if code == CREATE_THREAD_DEBUG_EVENT:
            set_hwbp_on_thread(de.dwThreadId, anchor)
        elif code == EXCEPTION_DEBUG_EVENT:
            er = de.u.Exception.ExceptionRecord
            ec = er.ExceptionCode & 0xffffffff
            addr = er.ExceptionAddress or 0
            if ec in (STATUS_SINGLE_STEP, STATUS_WX86_SINGLE_STEP) and addr == anchor:
                hits += 1
                th = k32.OpenThread(THREAD_ALL, False, de.dwThreadId)
                raw, ctx = aligned_ctx()
                k32.GetThreadContext(th, ctypes.byref(ctx))
                print(f"\n===== HIT {hits} @ RIP=0x{ctx.Rip:012x} (tid {de.dwThreadId}) =====", flush=True)
                reg = {"rax": ctx.Rax, "rcx": ctx.Rcx, "rdx": ctx.Rdx, "rbx": ctx.Rbx,
                       "rsi": ctx.Rsi, "rdi": ctx.Rdi, "rbp": ctx.Rbp, "rsp": ctx.Rsp,
                       "r8": ctx.R8, "r9": ctx.R9, "r10": ctx.R10, "r11": ctx.R11,
                       "r12": ctx.R12, "r13": ctx.R13, "r14": ctx.R14, "r15": ctx.R15}
                for rn, rv in reg.items():
                    ro = region_of(rv)
                    tag = ""
                    if ro:
                        b, s, p = ro
                        ex = (p & 0xff) in M.PAGE_EXEC
                        tag = f" -> region 0x{b:x}+0x{s:x} prot=0x{p:x}{' EXEC' if ex else ''}"
                    print(f"  {rn:3}=0x{rv:016x}{tag}")
                    if ro and not ((ro[2] & 0xff) in M.PAGE_EXEC):
                        d = M.read(hp, rv, 96)
                        if d:
                            print(f"       [{rn}]: {d[:48].hex(' ')}")
                            print(f"             {d[48:].hex(' ')}")
                # stack args
                st = M.read(hp, ctx.Rsp, 0x60)
                if st:
                    import struct
                    qs = struct.unpack_from("<12Q", st, 0)
                    print("  stack: " + " ".join(f"{q:012x}" for q in qs))
                # clear Dr6 so the next hit signals cleanly
                ctx.Dr6 = 0; ctx.ContextFlags = CTX_FLAGS
                k32.SetThreadContext(th, ctypes.byref(ctx))
                k32.CloseHandle(th)
            elif ec == STATUS_BREAKPOINT:
                pass   # initial attach breakpoint
            else:
                status = DBG_EXCEPTION_NOT_HANDLED
        k32.ContinueDebugEvent(de.dwProcessId, de.dwThreadId, status)

    # disarm: clear DR0/DR7 on all threads, detach
    for tid in all_thread_ids(pid):
        h = k32.OpenThread(THREAD_ALL, False, tid)
        if h:
            k32.SuspendThread(h)
            raw, ctx = aligned_ctx()
            if k32.GetThreadContext(h, ctypes.byref(ctx)):
                ctx.Dr0 = 0; ctx.Dr7 &= ~0x00000001; ctx.ContextFlags = CTX_FLAGS
                k32.SetThreadContext(h, ctypes.byref(ctx))
            k32.ResumeThread(h); k32.CloseHandle(h)
    k32.DebugActiveProcessStop(pid)
    k32.CloseHandle(hp)
    print(f"\n=== done: {hits} hit(s). {'GOT DATA' if hits else 'NO HIT — BP never reached (re-render not triggered, or VMProtect blocked the DR/attach).'}")


if __name__ == "__main__":
    sys.exit(main() or 0)
