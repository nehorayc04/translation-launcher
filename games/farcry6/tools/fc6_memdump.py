"""
Read-only process-memory scanner for a running FarCry6.exe.
Finds the decompressed oasis text in RAM (the engine keeps it after unpacking the
scheme-2 entry) by searching for known Arabic menu strings, then dumps context.

No admin needed (same-user, PROCESS_VM_READ only). No writes ever.

usage:
  python fc6_memdump.py find "متابعة اللعب"      # locate a string, show hits + context
  python fc6_memdump.py scan                      # search the built-in Arabic menu set
  python fc6_memdump.py dump <hexaddr> <len> out.bin
"""
import ctypes, ctypes.wintypes as w, sys, struct

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
k = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
# readable protections
READABLE = {0x02, 0x04, 0x20, 0x40}  # RO, RW, EXEC_READ, EXEC_RW

MENU = ["متابعة اللعب", "تحديد ملف حفظ اللعبة", "لعبة جديدة", "الإضافات",
        "المتجر", "الخيارات", "الخروج إلى سطح المكتب"]


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", w.DWORD), ("__a", w.DWORD), ("RegionSize", ctypes.c_ulonglong),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD), ("__b", w.DWORD)]


def find_pid(names=("FarCry6.exe",)):
    class PE(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", w.DWORD),
                    ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_char * 260)]
    snap = k.CreateToolhelp32Snapshot(0x2, 0)
    pe = PE(); pe.dwSize = ctypes.sizeof(PE)
    pid = None
    if k.Process32First(snap, ctypes.byref(pe)):
        while True:
            nm = pe.szExeFile.decode("latin-1")
            if nm in names:
                pid = pe.th32ProcessID; break
            if not k.Process32Next(snap, ctypes.byref(pe)):
                break
    k.CloseHandle(snap)
    return pid


def open_proc(pid):
    h = k.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise OSError(f"OpenProcess failed (err {ctypes.get_last_error()})")
    return h


def regions(h):
    mbi = MEMORY_BASIC_INFORMATION64()
    addr = 0
    while addr < 0x00007FFFFFFFFFFF:
        r = k.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not r:
            addr += 0x1000; continue
        if (mbi.State == MEM_COMMIT and mbi.Protect in READABLE
                and not (mbi.Protect & PAGE_GUARD) and mbi.RegionSize < (512 << 20)):
            yield mbi.BaseAddress, mbi.RegionSize
        addr = mbi.BaseAddress + mbi.RegionSize


def read(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if not k.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return None
    return buf.raw[:got.value]


def search(h, needles):
    """needles: list of (label, bytes). Yields (label, addr, region_base, region_size)."""
    for base, size in regions(h):
        data = read(h, base, size)
        if not data:
            continue
        for label, nb in needles:
            start = 0
            while True:
                i = data.find(nb, start)
                if i < 0:
                    break
                yield label, base + i, base, size, data
                start = i + 1


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    pid = find_pid()
    if not pid:
        print("FarCry6.exe is NOT running. Launch the game (Arabic), go to the main menu, leave it open.")
        return
    print(f"FarCry6.exe pid={pid}")
    h = open_proc(pid)
    if cmd == "dump":
        addr = int(sys.argv[2], 16); ln = int(sys.argv[3]); out = sys.argv[4]
        d = read(h, addr, ln); open(out, "wb").write(d or b"")
        print(f"dumped {len(d or b'')} bytes @ {addr:#x} -> {out}")
        return
    targets = [sys.argv[2]] if cmd == "find" and len(sys.argv) > 2 else MENU
    needles = []
    for t in targets:
        needles.append((f"{t} [utf16]", t.encode("utf-16-le")))
        needles.append((f"{t} [utf8]", t.encode("utf-8")))
    seen = 0
    for label, addr, base, size, data in search(h, needles):
        seen += 1
        # show a chunk of context around the hit
        off = addr - base
        ctx = data[max(0, off - 16):off + 96]
        print(f"HIT {label} @ {addr:#x} (region {base:#x}+{size:#x})")
        print("   ctx:", ctx[:80].hex(" "))
        if seen >= 40:
            print("... (capped at 40 hits)"); break
    if not seen:
        print("no hits — is the game at the Arabic main menu? try `find <exact on-screen string>`")


if __name__ == "__main__":
    main()
