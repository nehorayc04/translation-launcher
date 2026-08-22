# -*- coding: utf-8 -*-
r"""got_catch_rerender.py — attach at the MENU (no boot race), arm PAGE_GUARD on EVERY live
copy of the FontVerts store (tail-kind2), then rely on the USER to trigger a re-tessellation
(enter Settings / change Text Language). Catch the guard faults = the tessellator's vertex
reads, and print the distinct reading RIPs + accessed offsets.

Why this beats got_dbg_boot2: the boot render is one-time+cached, so arming after boot caught
nothing. At the menu the game is IDLE, so we arm calmly first; a user-triggered re-render then
re-fires the (uncached-for-new-glyphs) tessellation while our guard is already in place.

    python got_catch_rerender.py [seconds]      # attaches to the running game
Prints:  RIP <addr>  hits=<n>  offs=[...]        (feed the top RIP to memdump+capstone)
"""
import sys, os, ctypes, ctypes.wintypes as wt, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M
from got_dbg import DEBUG_EVENT

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
HERE = os.path.dirname(os.path.abspath(__file__))
DBG_CONTINUE = 0x00010002
DBG_NOT_HANDLED = 0x80010001
GUARD_STATUS = 0x80000001
SS_STATUS = 0x80000004
PAGE = 0x1000
GUARD = 0x100
PAGE_RW = 0x04
STORE_SPAN = 0x40000          # arm a generous 256 KB window from each SIG match
f = open(os.path.join(HERE, "..", "extract", "ghost_title.xpps"), "rb").read()
SIG = f[0x97c8d0:0x97c8d0 + 48]


def find_all(hp):
    """Return every live VA where the FontVerts SIG appears (multiple heap copies exist)."""
    hits = []
    for base, size, prot in M.regions(hp, exec_only=False):
        if (prot & 0xff) != PAGE_RW:
            continue
        if not (0x40000 <= size <= 0x1000000):   # ~0.25-16 MB private RW
            continue
        d = M.read(hp, base, size)
        if not d:
            continue
        o = 0
        while True:
            o = d.find(SIG, o)
            if o == -1:
                break
            hits.append(base + o)
            o += 1
    return hits


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
    pid = M.pid()
    if not pid:
        print("no game pid"); return 2
    hp = k32.OpenProcess(0x1F0FFF, False, pid)
    tails = find_all(hp)
    if not tails:
        print("tail-kind2 SIG not found yet (menu not rendered?). retry in a few s."); return 3
    print(f"pid={pid}; {len(tails)} FontVerts copies: " + ", ".join(hex(t) for t in tails))
    ranges = [(t, t + STORE_SPAN) for t in tails]

    if not k32.DebugActiveProcess(pid):
        print(f"DebugActiveProcess failed {ctypes.get_last_error()}"); return 4
    k32.DebugSetProcessKillOnExit(False)

    def arm_page(pg):
        old = wt.DWORD(0)
        k32.VirtualProtectEx(hp, ctypes.c_void_p(pg), PAGE, PAGE_RW | GUARD, ctypes.byref(old))

    def arm_all():
        for t in tails:
            base = t & ~(PAGE - 1)
            for i in range(0, STORE_SPAN // PAGE):
                arm_page(base + i * PAGE)

    arm_all()
    print(f"ARMED {len(tails)} regions x {STORE_SPAN//PAGE} pages. "
          f">>> NOW: in-game go to Settings / change Text Language to trigger a re-render. <<<")

    de = DEBUG_EVENT()
    hits = {}          # rip -> set(offset)
    t0 = time.time()
    last_rearm = 0
    while time.time() - t0 < secs:
        if k32.WaitForDebugEvent(ctypes.byref(de), 100):
            status = DBG_CONTINUE
            if de.dwDebugEventCode == 1:
                er = de.u.ExceptionRecord
                ec = er.ExceptionCode & 0xffffffff
                if ec == GUARD_STATUS:
                    acc = er.ExceptionInformation[1]
                    for lo, hi in ranges:
                        if lo <= acc < hi:
                            rip = er.ExceptionAddress or 0
                            s = hits.setdefault(rip, set())
                            s.add(acc - lo)
                            if len(s) == 1 or len(s) % 50 == 0:
                                print(f"  [hit] RIP=0x{rip:012x} off=0x{acc-lo:x} (rip seen {len(s)} offs)", flush=True)
                            break
                    arm_page(acc & ~(PAGE - 1))    # re-arm the touched page (guard is one-shot)
                elif ec == SS_STATUS:
                    pass
                else:
                    status = DBG_NOT_HANDLED
            k32.ContinueDebugEvent(de.dwProcessId, de.dwThreadId, status)
        # periodic full re-arm so a page touched once keeps catching later reads
        if time.time() - last_rearm > 3.0:
            last_rearm = time.time()
            arm_all()
        if sum(len(v) for v in hits.values()) >= 400:
            print("enough samples; stopping.")
            break

    k32.DebugActiveProcessStop(pid)
    k32.CloseHandle(hp)
    print(f"\n=== distinct reading RIPs: {len(hits)} ===")
    for rip in sorted(hits, key=lambda r: -len(hits[r])):
        offs = sorted(hits[rip])
        print(f"  RIP 0x{rip:012x}  reads={len(hits[rip])}  offs[0:12]={[hex(o) for o in offs[:12]]}")


if __name__ == "__main__":
    main()
