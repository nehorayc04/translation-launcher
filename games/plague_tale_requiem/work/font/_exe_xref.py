# -*- coding: utf-8 -*-
"""Fast RIP-relative xref finder + disassembler for the font-size hunt.
Finds every `lea rXX, [rip+disp]` in .text that points at a target string, then disassembles
around the hit so we can see how the UI style / font is built (and spot a size constant)."""
import struct, sys
import numpy as np
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

EXE = r"D:\Games\A Plague Tale - Requiem\APlagueTaleRequiem_x64.exe"
data = open(EXE, "rb").read()
buf = np.frombuffer(data, dtype=np.uint8)

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

TEXT = next(s for s in SECS if s[0] == ".text")
T_RA, T_RS, T_VA = TEXT[3], TEXT[4], TEXT[1]

# ---- vectorised lea scan over .text ----
t = buf[T_RA:T_RA + T_RS]
n = len(t) - 8
b0, b1, b2 = t[0:n], t[1:n + 1], t[2:n + 2]
REX = ((b0 >= 0x40) & (b0 <= 0x4F))
mask = REX & (b1 == 0x8D) & ((b2 & 0xC7) == 0x05)
idx = np.nonzero(mask)[0]
d = (t[3:n + 3].astype(np.int64) | (t[4:n + 4].astype(np.int64) << 8) |
     (t[5:n + 5].astype(np.int64) << 16) | (t[6:n + 6].astype(np.int64) << 24))
d = d[idx]
d = np.where(d >= 2**31, d - 2**32, d)
va_next = IMGBASE + T_VA + (idx + 7)          # VA of the instruction AFTER the lea
targets = va_next + d
print(f"scanned .text: {len(idx):,} rip-relative LEA instructions")

md = Cs(CS_ARCH_X86, CS_MODE_64)

def show(name, str_off, ctx_back=64, ctx_fwd=96):
    va = off2va(str_off)
    hits = np.nonzero(targets == va)[0]
    print(f"\n=== {name}  (str off 0x{str_off:08X}, VA 0x{va:X}) -> {len(hits)} xref(s) ===")
    for h in hits[:4]:
        ins_off = T_RA + int(idx[h])
        ins_va = off2va(ins_off)
        print(f"  --- lea @ file 0x{ins_off:08X} / VA 0x{ins_va:X} ---")
        start = max(T_RA, ins_off - ctx_back)
        code = data[start:ins_off + ctx_fwd]
        for ins in md.disasm(code, off2va(start)):
            mark = " <<<" if ins.address == ins_va else ""
            print(f"    {ins.address:012X}  {ins.mnemonic:<8} {ins.op_str}{mark}")

TARGETS = [
    ("text_PLGSubtitle_Small",  0x01882920),
    ("text_PLGSubtitle_Medium", 0x01882938),
    ("text_PLGSubtitle_Large",  0x01882950),
    ("BIG_ARABIC",              0x01B76AB8),
    ("FontSize",                0x01B727B8),
    ("SubtitlesSize",           0x01886C80),
]
for nm, off in TARGETS:
    show(nm, off)
