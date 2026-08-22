# -*- coding: utf-8 -*-
"""find_cmap_live.py — locate the RUNTIME cmap table by structural signature (C-speed regex).
Record = 64 B; +20 == 0xF8; +62..63 == FFFF; +0 = plausible codepoint."""
import sys, os, ctypes, struct, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M
k32 = ctypes.windll.kernel32
REC = re.compile(rb"\xf8[\s\S]{41}\xff\xff", re.S)      # anchor: +20 then +62

def regions(hp):
    mbi = M.MEMORY_BASIC_INFORMATION64(); a = 0; out = []
    while a < 0x7fffffffffff:
        if not k32.VirtualQueryEx(hp, ctypes.c_void_p(a), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if (mbi.State == 0x1000 and (mbi.Protect & 0xff) in (0x02, 0x04, 0x20, 0x40)
                and 0x10000 <= mbi.RegionSize <= 0x4000000):
            out.append((mbi.BaseAddress, mbi.RegionSize))
        a = mbi.BaseAddress + mbi.RegionSize
        if mbi.RegionSize == 0: a += 0x1000
    return out

def isrec(b, o):
    if o < 0 or o + 64 > len(b): return False
    if b[o+20] != 0xF8 or b[o+62] != 0xFF or b[o+63] != 0xFF: return False
    cp = struct.unpack_from("<I", b, o)[0]
    return 0x20 <= cp < 0x110000

def main():
    pid = M.pid(); hp = M.open_proc(pid)
    regs = regions(hp); print(f"pid {pid}: {len(regs)} regions", flush=True)
    found = []; t0 = time.time()
    for i, (base, size) in enumerate(regs):
        data = M.read(hp, base, size)
        if not data: continue
        for m in REC.finditer(data):
            o = m.start() - 20
            if not isrec(data, o): continue
            if o >= 64 and isrec(data, o - 64): continue      # not the table head
            n = 0; j = o
            while isrec(data, j): n += 1; j += 64
            if n >= 8:
                cps = [struct.unpack_from("<I", data, o + 64*k)[0] for k in range(min(n, 8))]
                found.append((base + o, n, cps))
        if i % 200 == 0:
            print(f"  ..{i}/{len(regs)} ({time.time()-t0:.0f}s) hits={len(found)}", flush=True)
    print(f"\n== {len(found)} cmap-like tables ==", flush=True)
    for va, n, cps in sorted(found, key=lambda x: -x[1])[:15]:
        print(f"  VA 0x{va:012x}  n={n:5}  " + " ".join(f"U+{c:04X}" for c in cps), flush=True)
    k32.CloseHandle(hp)

if __name__ == "__main__":
    main()
