# -*- coding: utf-8 -*-
"""Hunt the FONT TABLE / font-size data in the exe.
1. locate every font-name string
2. hex-dump around the clusters (a per-font struct would show floats/ints between names)
3. compute each string's VA and find POINTERS to it (a table of {name*, ...}) and RIP-relative
   LEA references in .text (the code that uses the name)."""
import struct, re

EXE = r"D:\Games\A Plague Tale - Requiem\APlagueTaleRequiem_x64.exe"
data = open(EXE, "rb").read()

# ---- section map for off<->VA ----
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, e_lfanew + 6)[0]
opt_size = struct.unpack_from("<H", data, e_lfanew + 20)[0]
opt_off = e_lfanew + 24
IMGBASE = struct.unpack_from("<Q", data, opt_off + 24)[0]
sec_off = opt_off + opt_size
SECS = []
for i in range(nsec):
    o = sec_off + i * 40
    nm = data[o:o + 8].rstrip(b"\0").decode("latin1")
    vs, va, rs, ra = struct.unpack_from("<IIII", data, o + 8)[0], 0, 0, 0
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
    SECS.append((nm, vaddr, vsize, raddr, rsize))

def off2va(off):
    for nm, va, vs, ra, rs in SECS:
        if ra <= off < ra + rs:
            return IMGBASE + va + (off - ra)
    return None

def va2off(va):
    r = va - IMGBASE
    for nm, vaddr, vs, ra, rs in SECS:
        if vaddr <= r < vaddr + max(vs, rs):
            return ra + (r - vaddr)
    return None

def sec_of(off):
    for nm, va, vs, ra, rs in SECS:
        if ra <= off < ra + rs:
            return nm
    return "?"

NAMES = [b"BIG_FONT", b"SMALL_FONT_02", b"SMALL_FONT", b"BIG_RUS", b"BIG_JAP",
         b"BIG_KOR", b"BIG_CHI", b"BIG_ARABIC", b"DEBUG_FONT"]
print("=== font-name strings ===")
locs = {}
for n in NAMES:
    for m in re.finditer(re.escape(n) + rb"\x00", data):
        off = m.start()
        va = off2va(off)
        locs.setdefault(n, []).append((off, va))
        print(f"  {n.decode():14} off=0x{off:08X} sec={sec_of(off):8} VA=0x{va:X}" if va else
              f"  {n.decode():14} off=0x{off:08X} (no VA)")

# ---- hex dump around the cluster ----
def dump(start, length, label):
    print(f"\n--- {label} (off 0x{start:08X}) ---")
    for r in range(0, length, 16):
        chunk = data[start + r: start + r + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print(f"  {start+r:08X}  {hexs:<47}  {asc}")

dump(0x01B72900, 0xC0, "cluster A (BIG_FONT / BIG_RUS / SMALL_FONT)")
dump(0x01B76A80, 0x80, "cluster B (BIG_ARABIC / DEBUG_FONT)")

# ---- pointers to those strings (a font table) ----
print("\n=== 8-byte POINTERS to the font-name strings (=> a font table) ===")
for n, lst in locs.items():
    for off, va in lst:
        if va is None:
            continue
        pat = struct.pack("<Q", va)
        for m in re.finditer(re.escape(pat), data):
            p = m.start()
            print(f"  ptr@0x{p:08X} ({sec_of(p)}) -> {n.decode()}")

# ---- RIP-relative LEA refs in .text: 48 8D ?? ?? disp32 ----
print("\n=== RIP-relative refs from .text (lea rXX, [rip+disp]) ===")
text = next(s for s in SECS if s[0] == ".text")
t_ra, t_rs, t_va = text[3], text[4], text[1]
for n, lst in locs.items():
    for off, va in lst:
        if va is None:
            continue
        hits = 0
        for i in range(t_ra, t_ra + t_rs - 7):
            if data[i] == 0x48 and data[i + 1] == 0x8D:
                disp = struct.unpack_from("<i", data, i + 3)[0]
                nxt = off2va(i + 7)
                if nxt is not None and nxt + disp == va:
                    print(f"  lea @0x{i:08X} (VA 0x{off2va(i):X}) -> {n.decode()}")
                    hits += 1
                    if hits > 6:
                        break
