# -*- coding: utf-8 -*-
r"""got_anchor.py — locate the tessellator CODE anchor for the CURRENT (ASLR) launch.

Prior sessions found, at exe base 0x7ff7f20d1000:
  * GENERATE_QUAD xref (tessellator)   @ 0x7ff7f220461f  -> RVA 0x13361f
  * FONT_KIND     xref (reflection)    @ 0x7ff7f22047a6  -> RVA 0x1336a6
This rebases those RVAs onto the live module base, prints the current anchor VAs, and
cross-checks by locating the GENERATE_QUAD / FontVerts / SFontData strings in memory.
If capstone is present it disassembles 0x40 bytes at each anchor and flags a `lea reg,[rip+..]`
that resolves to the GENERATE_QUAD string (= proof the rebase is right and the code is NOT
VM-virtualized). Run with the repo .venv python while the game sits at the menu.
"""
import sys, os, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memdump as M

k32 = ctypes.windll.kernel32
psapi = ctypes.WinDLL("psapi", use_last_error=True)
RVA_TESS = 0x13361f      # GENERATE_QUAD xref = the tessellator
RVA_FK   = 0x1336a6      # FONT_KIND xref = reflection/schema (avoid)
OLD_BASE = 0x7ff7f20d1000


def module_base(pid):
    # ctypes defaults to 32-bit int args -> a 64-bit module handle (0x7ff7...) gets TRUNCATED.
    # Declare argtypes/restype and pass handles as c_void_p so nothing truncates.
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    enum = getattr(psapi, "EnumProcessModulesEx", None) or getattr(k32, "K32EnumProcessModulesEx")
    getname = getattr(psapi, "GetModuleFileNameExW", None) or getattr(k32, "K32GetModuleFileNameExW")
    enum.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
    enum.restype = wt.BOOL
    getname.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
    getname.restype = wt.DWORD

    h = k32.OpenProcess(0x0410, False, pid)   # QUERY_INFORMATION | VM_READ
    if not h:
        return None, None
    arr = (ctypes.c_void_p * 4096)()
    needed = wt.DWORD()
    if not enum(h, arr, ctypes.sizeof(arr), ctypes.byref(needed), 0x03):
        print(f"   EnumProcessModulesEx err={ctypes.get_last_error()}")
        k32.CloseHandle(h); return None, None
    n = min(len(arr), needed.value // ctypes.sizeof(ctypes.c_void_p))
    base = name = None
    for i in range(n):
        mod = arr[i]
        if not mod:
            continue
        buf = ctypes.create_unicode_buffer(512)
        if getname(h, ctypes.c_void_p(mod), buf, 512) and "ghostoftsushima.exe" in buf.value.lower():
            base = mod; name = buf.value; break
    k32.CloseHandle(h)
    return base, name


def find_string_vas(hp, needle, limit=6):
    hits = []
    for base, size, prot in M.regions(hp, exec_only=False):
        d = M.read(hp, base, size)
        if not d:
            continue
        o = d.find(needle)
        while o != -1 and len(hits) < limit:
            hits.append((base + o, (prot & 0xff) in M.PAGE_EXEC))
            o = d.find(needle, o + 1)
    return hits


def scan_lea_to(hp, target_vas):
    """Find every `lea reg,[rip+disp32]` (48/4C 8D, modrm rm=101) whose target is a wanted VA."""
    tset = set(target_vas)
    hits = []
    for base, size, prot in M.regions(hp, exec_only=True):
        d = M.read(hp, base, size)
        if not d:
            continue
        n = len(d); i = 0
        while i < n - 6:
            if d[i] in (0x48, 0x4C) and d[i + 1] == 0x8D and (d[i + 2] & 0xC7) == 0x05:
                disp = int.from_bytes(d[i + 3:i + 7], "little", signed=True)
                site = base + i
                tgt = (site + 7 + disp) & 0xffffffffffffffff
                if tgt in tset:
                    hits.append((site, tgt))
                i += 7
            else:
                i += 1
    return hits


def main():
    pid = M.pid()
    if not pid:
        print("!! GhostOfTsushima.exe not running — launch it to the MAIN MENU first."); return 2
    hp = M.open_proc(pid)

    print("-- font strings in live memory --")
    gq = [s for s, _ in find_string_vas(hp, b"GENERATE_QUAD")]
    fk = [s for s, _ in find_string_vas(hp, b"FONT_KIND")]
    for s in gq:
        print(f"   GENERATE_QUAD @ 0x{s:012x}")
    for s in fk:
        print(f"   FONT_KIND     @ 0x{s:012x}")
    for lbl in (b"FontVerts", b"SFontData", b"FontGlyphs"):
        for s, ex in find_string_vas(hp, lbl, 2):
            print(f"   {lbl.decode():11} @ 0x{s:012x}")

    if not gq:
        print("!! GENERATE_QUAD string not found in memory (menu not rendered yet?)"); k32.CloseHandle(hp); return 4

    print("\n-- scanning exec memory for `lea reg,[rip]->GENERATE_QUAD` (the tessellator xref) --")
    sites = scan_lea_to(hp, gq)
    if not sites:
        print("!! no lea->GENERATE_QUAD found (code may be VM-virtualized here).");
    for site, tgt in sites:
        derived_base = site - RVA_TESS
        aligned = (derived_base & 0xfff) == 0
        print(f"   lea @ 0x{site:012x} -> GENERATE_QUAD 0x{tgt:012x}   "
              f"derived exe_base=0x{derived_base:012x} {'(page-aligned OK)' if aligned else '(NOT aligned -> different xref)'}")

    # capstone disasm around each candidate to confirm it is real code + read the neighbours
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
    gqset = set(gq); fkset = set(fk)
    anchors = []
    for site, _ in sites:
        base = site - RVA_TESS
        anchors.append(site)
        print(f"\n-- disasm around candidate anchor 0x{site:012x} (exe_base 0x{base:012x}) --")
        code = M.read(hp, site - 0x18, 0x50)
        if not code:
            print("   READ FAILED"); continue
        for ins in md.disasm(code, site - 0x18):
            note = ""
            if ins.mnemonic == "lea" and "rip" in ins.op_str:
                try:
                    t = ins.address + ins.size + ins.operands[1].mem.disp
                    if t in gqset: note = "   -> GENERATE_QUAD"
                    elif t in fkset: note = "   -> FONT_KIND"
                    else: note = f"   -> 0x{t:x}"
                except Exception:
                    pass
            mark = "  <== BREAKPOINT HERE" if ins.address == site else ""
            print(f"   0x{ins.address:012x}: {ins.mnemonic:9} {ins.op_str}{note}{mark}")

    k32.CloseHandle(hp)
    if anchors:
        print("\n>>> ANCHOR(s) to breakpoint: " + ", ".join(f"0x{a:x}" for a in anchors))
        print(f">>> primary tessellator anchor = 0x{anchors[0]:012x}")
    print("\nNEXT: python work/got_codebp.py <anchor_va>")


if __name__ == "__main__":
    sys.exit(main() or 0)
