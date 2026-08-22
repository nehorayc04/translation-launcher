# -*- coding: utf-8 -*-
"""Standalone SCANNER: find tail-kind2's VA in the target process ASAP and arm PAGE_GUARD on
all its pages, so the (separate) debugger process catches the tessellator's read. Runs in its
OWN process => no GIL contention with the debugger's WaitForDebugEvent loop (that contention
was freezing the game and stalling boot). Writes the found tail_va to <tvfile>."""
import sys, os, time, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

PAGE = 0x1000
pid = int(sys.argv[1])
tvfile = sys.argv[2]
f = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract", "ghost_title.xpps"), "rb").read()
SIG = f[0x97c8d0:0x97c8d0 + 48]

hp = M.k32.OpenProcess(0x1F0FFF, False, pid)


def arm_all(base):
    old = wt.DWORD(0)
    for i in range(0, 42):
        M.k32.VirtualProtectEx(hp, ctypes.c_void_p(base + i * PAGE), PAGE, 0x04 | 0x100, ctypes.byref(old))


def scan():
    # FAST filter: the tail-kind2 section loads into a ~2 MB PRIVATE READWRITE allocation
    # (measured: prot=0x04, RegionSize~1.7-2 MB). Scan only 0.5-8 MB RW regions -> a handful,
    # so we arm within ~1 s of the font landing (before the one-time render caches it).
    for base, size, prot in M.regions(hp, exec_only=False):
        if (prot & 0xff) != 0x04:
            continue
        if not (0x80000 <= size <= 0x800000):
            continue
        d = M.read(hp, base, size)
        if d:
            o = d.find(SIG)
            if o != -1:
                return base + o
    return None


tv = None
t0 = time.time()
npass = 0
while time.time() - t0 < 200:
    if tv is None:
        npass += 1
        tv = scan()
        if tv:
            open(tvfile, "w").write(hex(tv))
            arm_all(tv & ~(PAGE - 1))
            print(f"[scan] tail_va={tv:#x} ARMED t+{time.time()-t0:.1f}s (pass {npass})", flush=True)
        # no sleep: scan as fast as possible to arm within ~1-2s of the font loading
    else:
        time.sleep(0.4)
        arm_all(tv & ~(PAGE - 1))   # re-arm (guard is one-shot per fault) to keep catching
