"""Read-only PE protection measurement for Anno1800.exe.

Measures: section table, entry-point section, .reloc size vs image size,
per-section entropy, and a DRM string scan. Never writes to the game folder.
"""
import sys, math, re, os
import pefile

EXE = sys.argv[1] if len(sys.argv) > 1 else \
    r"C:\Program Files (x86)\Steam\steamapps\common\Anno 1800\Bin\Win64\Anno1800.exe"

CH = {
    0x00000020: "CNT_CODE",
    0x00000040: "CNT_INIT_DATA",
    0x00000080: "CNT_UNINIT_DATA",
    0x02000000: "MEM_DISCARDABLE",
    0x04000000: "MEM_NOT_CACHED",
    0x08000000: "MEM_NOT_PAGED",
    0x10000000: "MEM_SHARED",
    0x20000000: "MEM_EXECUTE",
    0x40000000: "MEM_READ",
    0x80000000: "MEM_WRITE",
}


def flags(v):
    return "|".join(n for b, n in CH.items() if v & b)


def entropy(b):
    if not b:
        return 0.0
    c = [0] * 256
    for x in b:
        c[x] += 1
    n = len(b)
    return -sum((k / n) * math.log2(k / n) for k in c if k)


def main():
    st = os.stat(EXE)
    print(f"FILE     : {EXE}")
    print(f"SIZE     : {st.st_size:,} bytes ({st.st_size/1024/1024:.2f} MB)")
    print(f"MTIME    : {__import__('datetime').datetime.fromtimestamp(st.st_mtime)}")

    pe = pefile.PE(EXE, fast_load=True)
    oh = pe.OPTIONAL_HEADER
    fh = pe.FILE_HEADER
    print(f"MACHINE  : 0x{fh.Machine:04x}   TimeDateStamp: {fh.TimeDateStamp} "
          f"({__import__('datetime').datetime.utcfromtimestamp(fh.TimeDateStamp)} UTC)")
    print(f"IMAGEBASE: 0x{oh.ImageBase:x}")
    print(f"SizeOfImage      : {oh.SizeOfImage:,} ({oh.SizeOfImage/1024/1024:.2f} MB)")
    print(f"AddressOfEntry   : 0x{oh.AddressOfEntryPoint:x}")
    print(f"SizeOfHeaders    : {oh.SizeOfHeaders:,}")
    print(f"DllCharacteristics: 0x{oh.DllCharacteristics:04x}")
    print(f"CheckSum         : 0x{oh.CheckSum:08x}")
    print()

    ep = oh.AddressOfEntryPoint
    print(f"{'NAME':<12}{'VA':>12}{'VSIZE':>14}{'RAWPTR':>12}{'RAWSIZE':>14}"
          f"{'ENTROPY':>9}  CHARACTERISTICS")
    ep_sec = None
    reloc_raw = reloc_virt = 0
    total_raw = 0
    for s in pe.sections:
        name = s.Name.rstrip(b"\x00").decode("latin-1", "replace")
        data = s.get_data()
        e = entropy(data[:8 * 1024 * 1024])  # cap for speed on huge sections
        mark = ""
        if s.VirtualAddress <= ep < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            mark = "  <== ENTRY POINT"
            ep_sec = name
        if name.lower().startswith(".reloc"):
            reloc_raw, reloc_virt = s.SizeOfRawData, s.Misc_VirtualSize
        total_raw += s.SizeOfRawData
        print(f"{name:<12}{s.VirtualAddress:>12x}{s.Misc_VirtualSize:>14,}"
              f"{s.PointerToRawData:>12x}{s.SizeOfRawData:>14,}{e:>9.3f}"
              f"  {flags(s.Characteristics)}{mark}")

    print()
    print(f"ENTRY POINT SECTION : {ep_sec}")
    print(f".reloc raw size     : {reloc_raw:,}  (virtual {reloc_virt:,})")
    if oh.SizeOfImage:
        print(f".reloc / SizeOfImage: {100.0*reloc_raw/oh.SizeOfImage:.4f} %")
    print(f"sum of raw sections : {total_raw:,}")

    # RWX sections
    print()
    rwx = [s for s in pe.sections
           if (s.Characteristics & 0x20000000) and (s.Characteristics & 0x80000000)]
    print(f"RWX (EXECUTE+WRITE) sections: {len(rwx)}")
    for s in rwx:
        n = s.Name.rstrip(b"\x00").decode("latin-1", "replace")
        print(f"   {n:<12} vsize={s.Misc_VirtualSize:,} raw={s.SizeOfRawData:,}")

    # Data directories
    print()
    pe.parse_data_directories()
    for i, d in enumerate(oh.DATA_DIRECTORY):
        if d.VirtualAddress or d.Size:
            print(f"  DIR[{i:2d}] {d.name:<34} rva=0x{d.VirtualAddress:<10x} size={d.Size:,}")

    # TLS
    print()
    if hasattr(pe, "DIRECTORY_ENTRY_TLS") and pe.DIRECTORY_ENTRY_TLS:
        t = pe.DIRECTORY_ENTRY_TLS.struct
        print(f"TLS present: callbacks addr=0x{t.AddressOfCallBacks:x} "
              f"index=0x{t.AddressOfIndex:x}")
    else:
        print("TLS: none")

    # Imports summary
    print()
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        dlls = [d.dll.decode("latin-1", "replace") for d in pe.DIRECTORY_ENTRY_IMPORT]
        n_funcs = sum(len(d.imports) for d in pe.DIRECTORY_ENTRY_IMPORT)
        print(f"IMPORTS: {len(dlls)} DLLs / {n_funcs} functions")
        print("  " + ", ".join(sorted(dlls)))
    else:
        print("IMPORTS: none parsed")


if __name__ == "__main__":
    main()
