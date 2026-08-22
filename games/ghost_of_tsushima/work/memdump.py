# -*- coding: utf-8 -*-
r"""memdump.py — dump the RUNNING GhostOfTsushima.exe's committed memory (defeats VMProtect
section-packing: the code is decrypted in RAM at runtime). Same-user/same-integrity, so
ReadProcessMemory works WITHOUT admin. Then we capstone the executable regions to find the
SFontData/FontVerts store decoder + GENERATE_QUAD tessellator (the authoritative font codec).

    python memdump.py dump  <out_prefix>   # dump all committed regions -> <prefix>.<addr>.bin + index
    python memdump.py strings <prefix>     # find font strings + their addresses in the dump
    python memdump.py exec   <out_prefix>  # dump ONLY executable regions (code)
Env: nothing. Run with the repo .venv python (capstone optional for disasm step).
"""
import sys, ctypes, ctypes.wintypes as wt, subprocess, os, struct

k32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
PAGE_EXEC = {0x10, 0x20, 0x40, 0x80}  # EXECUTE, EXECUTE_READ, EXECUTE_READWRITE, EXECUTE_WRITECOPY
EXE = "GhostOfTsushima.exe"


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong),
                ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", wt.DWORD),
                ("__alignment1", wt.DWORD),
                ("RegionSize", ctypes.c_ulonglong),
                ("State", wt.DWORD),
                ("Protect", wt.DWORD),
                ("Type", wt.DWORD),
                ("__alignment2", wt.DWORD)]


def pid():
    o = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE}", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True).stdout
    for l in o.splitlines():
        p = [x.strip('"') for x in l.split('","')]
        if len(p) >= 2 and p[0].lower().startswith("ghost"):
            try:
                return int(p[1])
            except ValueError:
                pass
    return None


def open_proc(pd):
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pd)
    if not h:
        raise OSError(f"OpenProcess failed err={ctypes.get_last_error()}")
    return h


def regions(h, exec_only=False):
    mbi = MEMORY_BASIC_INFORMATION64()
    addr = 0
    out = []
    while addr < 0x7fffffffffff:
        r = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not r:
            break
        if mbi.State == MEM_COMMIT and mbi.RegionSize < 0x8000000:  # skip huge (>128MB) heaps
            if not exec_only or (mbi.Protect & 0xff) in PAGE_EXEC:
                out.append((mbi.BaseAddress, mbi.RegionSize, mbi.Protect))
        addr = mbi.BaseAddress + mbi.RegionSize
        if mbi.RegionSize == 0:
            addr += 0x1000
    return out


def read(h, base, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, size, ctypes.byref(got))
    if not ok:
        return None
    return buf.raw[:got.value]


def do_dump(prefix, exec_only):
    pd = pid()
    if not pd:
        print("game not running"); return 2
    h = open_proc(pd)
    regs = regions(h, exec_only)
    idx = open(prefix + ".index.txt", "w")
    total = 0
    n = 0
    for base, size, prot in regs:
        data = read(h, base, size)
        if not data:
            continue
        with open(f"{prefix}.{base:012x}.bin", "wb") as f:
            f.write(data)
        idx.write(f"0x{base:012x} size=0x{size:x} prot=0x{prot:x} exec={(prot & 0xff) in PAGE_EXEC}\n")
        total += len(data); n += 1
    idx.close()
    print(f"dumped {n} regions, {total:,} bytes -> {prefix}.*.bin (index: {prefix}.index.txt)")
    k32.CloseHandle(h)


def do_strings(prefix):
    """Find the font-code strings in the dumped regions + their virtual addresses."""
    import glob
    targets = [b"FontVerts", b"SFontData", b"FontGlyphs", b"GENERATE_QUAD", b"FONTK",
               b"FONT_KIND", b"FONT_SIZE", b"SET_TEXT_DIRECT"]
    for fn in sorted(glob.glob(prefix + ".*.bin")):
        base = int(fn.split(".")[-2], 16)
        data = open(fn, "rb").read()
        for t in targets:
            off = data.find(t)
            while off != -1:
                print(f"  {t.decode():16} @ VA 0x{base + off:012x} (file {os.path.basename(fn)}+0x{off:x})")
                off = data.find(t, off + 1)


def do_live(patterns):
    """Search ALL committed regions of the running process for byte patterns; report VAs.
    patterns = list of (label, bytes)."""
    pd = pid()
    if not pd:
        print("game not running"); return 2
    h = open_proc(pd)
    regs = regions(h, exec_only=False)
    print(f"searching {len(regs)} committed regions...")
    for base, size, prot in regs:
        data = read(h, base, size)
        if not data:
            continue
        ex = (prot & 0xff) in PAGE_EXEC
        for label, pat in patterns:
            off = data.find(pat)
            cnt = 0
            while off != -1 and cnt < 4:
                print(f"  {label:22} @ VA 0x{base + off:012x}  (region 0x{base:x} prot=0x{prot:x} exec={ex})")
                cnt += 1
                off = data.find(pat, off + 1)
    k32.CloseHandle(h)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dump"
    if cmd == "live":
        pats = [(b"FontVerts", b"FontVerts"), (b"SFontData", b"SFontData"),
                (b"FontGlyphs", b"FontGlyphs"), (b"GENERATE_QUAD", b"GENERATE_QUAD"),
                (b"FONTK", b"FONTK"), (b"FONT_KIND", b"FONT_KIND"),
                ("store_notdef_unit", bytes.fromhex("af4f663e9270bd11")),
                ("store_unitB", bytes.fromhex("b7f87c6e102c74b7"))]
        pats = [(l if isinstance(l, str) else l.decode(), p) for l, p in pats]
        sys.exit(do_live(pats) or 0)
    if cmd == "dump":
        sys.exit(do_dump(sys.argv[2] if len(sys.argv) > 2 else "gotmem", False) or 0)
    elif cmd == "exec":
        sys.exit(do_dump(sys.argv[2] if len(sys.argv) > 2 else "gotmem", True) or 0)
    elif cmd == "strings":
        do_strings(sys.argv[2] if len(sys.argv) > 2 else "gotmem")
