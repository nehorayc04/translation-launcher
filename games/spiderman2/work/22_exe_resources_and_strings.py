"""Two-prong final check:
  1. Walk Spider-Man2.exe for PE resources of type RT_FONT (0x08)
  2. Get ALL strings in the exe ending in .ttf / .otf / .woff with their context"""
import os, sys, struct, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
EXE  = os.path.join(GAME, "Spider-Man2.exe")
data = open(EXE, "rb").read()
print(f"[*] exe = {len(data)} bytes")

# ---- 1. PE resource walk for RT_FONT (id 8) ----
# DOS header at 0, e_lfanew at 0x3C points to PE header.
e_lfanew = struct.unpack("<I", data[0x3C:0x40])[0]
pe_sig = data[e_lfanew:e_lfanew+4]
print(f"[*] PE sig at {hex(e_lfanew)}: {pe_sig}")  # should be "PE\0\0"
# Optional header start: e_lfanew + 4 + 20 (file header) = e_lfanew + 24
opt_header_start = e_lfanew + 24
# Magic word at opt_header_start: 0x10B (PE32) or 0x20B (PE32+)
magic = struct.unpack("<H", data[opt_header_start:opt_header_start+2])[0]
print(f"[*] optional header magic: {hex(magic)} ({'PE32+' if magic == 0x20b else 'PE32'})")
# Data directories live at fixed offsets after opt header.
# For PE32+: directories start at opt_header_start + 112 (NumberOfRvaAndSizes is at +108)
dirs_start = opt_header_start + 112
# DataDirectory[2] = Resource Table (RVA + Size, 8 bytes each)
res_rva = struct.unpack("<I", data[dirs_start + 2*8 : dirs_start + 2*8 + 4])[0]
res_size = struct.unpack("<I", data[dirs_start + 2*8 + 4 : dirs_start + 2*8 + 8])[0]
print(f"[*] Resource Directory: RVA=0x{res_rva:X} size={res_size}")

# Convert RVA to file offset using section headers
# Section headers start at e_lfanew + 24 + SizeOfOptionalHeader (from FileHeader)
size_of_opt = struct.unpack("<H", data[e_lfanew + 24 - 4 : e_lfanew + 24 - 2])[0]
num_sections = struct.unpack("<H", data[e_lfanew + 6 : e_lfanew + 8])[0]
sec_start = opt_header_start + size_of_opt
print(f"[*] {num_sections} sections, headers at 0x{sec_start:X}")

sections = []
for i in range(num_sections):
    h = data[sec_start + i*40 : sec_start + (i+1)*40]
    name = h[:8].split(b"\x00")[0].decode("ascii", "replace")
    vsize = struct.unpack("<I", h[8:12])[0]
    vaddr = struct.unpack("<I", h[12:16])[0]
    raw_size = struct.unpack("<I", h[16:20])[0]
    raw_ptr = struct.unpack("<I", h[20:24])[0]
    sections.append((name, vaddr, vsize, raw_ptr, raw_size))

def rva_to_off(rva):
    for name, vaddr, vsize, raw_ptr, raw_size in sections:
        if vaddr <= rva < vaddr + vsize:
            return raw_ptr + (rva - vaddr)
    return None

if res_rva and res_size:
    res_off = rva_to_off(res_rva)
    print(f"[*] resource directory file offset: 0x{res_off:X}")

    # Resource Directory Table layout (16 bytes):
    # u32 Characteristics, u32 TimeDateStamp, u16 MajorVer, u16 MinorVer,
    # u16 NumberOfNameEntries, u16 NumberOfIdEntries
    cur = res_off
    chars, tds, maj, mi, num_names, num_ids = struct.unpack("<IIHHHH", data[cur:cur+16])
    print(f"[*] root: name_entries={num_names}  id_entries={num_ids}")
    # Each entry is 8 bytes: u32 Name/Id, u32 Offset (high bit = subdirectory)
    entries = []
    for i in range(num_names + num_ids):
        eoff = cur + 16 + i*8
        e_id, e_off = struct.unpack("<II", data[eoff:eoff+8])
        entries.append((e_id, e_off, i < num_names))
    print(f"[*] root entries (by type id):")
    TYPE_NAMES = {1:"CURSOR",2:"BITMAP",3:"ICON",4:"MENU",5:"DIALOG",6:"STRING",
                  7:"FONTDIR",8:"FONT",9:"ACCELERATOR",10:"RCDATA",11:"MESSAGETABLE",
                  12:"GROUP_CURSOR",14:"GROUP_ICON",16:"VERSION",17:"DLGINCLUDE",
                  19:"PLUGPLAY",20:"VXD",21:"ANICURSOR",22:"ANIICON",23:"HTML",
                  24:"MANIFEST"}
    for e_id, e_off, is_name in entries:
        tname = TYPE_NAMES.get(e_id, f"<{e_id}>")
        is_subdir = bool(e_off & 0x80000000)
        print(f"   type_id={e_id} ({tname})  off=0x{e_off&0x7FFFFFFF:X}  is_subdir={is_subdir}")

# ---- 2. ALL .ttf/.otf strings with full context ----
print()
print("=== all strings ending in .ttf / .otf in the exe (with 80-char context) ===")
# Find each occurrence, walk back to last NUL or non-printable, walk forward similarly
for ext in (b".ttf", b".otf", b".woff", b".woff2", b".ttc"):
    i = 0; n = 0
    while True:
        j = data.find(ext, i)
        if j < 0: break
        # Walk back to NUL or non-printable
        start = j
        while start > 0 and (0x20 <= data[start-1] <= 0x7E):
            start -= 1
        # Walk forward
        end = j + len(ext)
        while end < len(data) and (0x20 <= data[end] <= 0x7E):
            end += 1
        s = data[start:end].decode("ascii", "replace")
        if 4 <= len(s) <= 200:
            print(f"  [{j:>9}] {ext.decode():<7}  {s!r}")
            n += 1
        i = j + len(ext)
        if n >= 20: break

# ---- 3. extra: search for cohtml://uiresources/ paths in exe ----
print()
print("=== uiresources / coui paths in exe ===")
for prefix in (b"coui://", b"cohtml://", b"uiresources/", b"uiresources\\"):
    c = data.count(prefix)
    if c:
        print(f"  {prefix!r} -> {c} hits")
        i = 0; n = 0
        while n < 10:
            j = data.find(prefix, i)
            if j < 0: break
            # extract printable run
            end = j
            while end < len(data) and (0x20 <= data[end] <= 0x7E):
                end += 1
            s = data[j:end].decode("ascii", "replace")
            if 0 < len(s) < 250:
                print(f"    [{j:>9}] {s!r}")
                n += 1
            i = j + 1
