# -*- coding: utf-8 -*-
"""EXE recon for the font-size hunt.
STEP 1: is APlagueTaleRequiem_x64.exe packed/protected? (packed => static patch is dead)
STEP 2: where do the font NAMES live? the game loads 'FONTES\\BIG_ARABIC' etc, so those strings
        are in the binary — a per-font size/family table may sit near them.
Pure stdlib PE parsing (no pefile dependency)."""
import struct, sys, math, re
from collections import Counter

EXE = r"D:\Games\A Plague Tale - Requiem\APlagueTaleRequiem_x64.exe"
data = open(EXE, "rb").read()
print(f"size = {len(data):,} bytes")

# ---------- PE headers ----------
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0", "not a PE"
machine, nsec, tstamp = struct.unpack_from("<HHI", data, e_lfanew + 4)
opt_size = struct.unpack_from("<H", data, e_lfanew + 20)[0]
opt_off = e_lfanew + 24
magic = struct.unpack_from("<H", data, opt_off)[0]
ep = struct.unpack_from("<I", data, opt_off + 16)[0]
imgbase = struct.unpack_from("<Q", data, opt_off + 24)[0]
print(f"machine={machine:04X} sections={nsec} PE32+={magic==0x20B} entry_rva=0x{ep:X} imagebase=0x{imgbase:X}")

sec_off = opt_off + opt_size
secs = []
for i in range(nsec):
    o = sec_off + i * 40
    name = data[o:o + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
    chars = struct.unpack_from("<I", data, o + 36)[0]
    secs.append((name, vaddr, vsize, raddr, rsize, chars))

def ent(b):
    if not b: return 0.0
    c = Counter(b); n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())

print(f"\n{'name':10} {'vaddr':>10} {'vsize':>11} {'raddr':>10} {'rsize':>11} {'chars':>10}  entropy  flags")
ep_sec = None
for name, va, vs, ra, rs, ch in secs:
    e = ent(data[ra:ra + min(rs, 2_000_000)])
    fl = []
    if ch & 0x20000000: fl.append("EXEC")
    if ch & 0x80000000: fl.append("WRITE")
    if ch & 0x40000000: fl.append("READ")
    if ep >= va and ep < va + max(vs, rs):
        ep_sec = name
    print(f"{name:10} {va:>10X} {vs:>11,} {ra:>10X} {rs:>11,} {ch:>10X}  {e:6.3f}  {'+'.join(fl)}")
print(f"\nentry point is in section: {ep_sec}")

# ---------- packer signatures ----------
sigs = {
    "VMProtect": [b".vmp0", b".vmp1", b".vmp2", b"VMProtect"],
    "Themida/WinLicense": [b".themida", b"Themida", b"WinLicense"],
    "Denuvo": [b"denuvo", b"Denuvo", b"DENUVO"],
    "UPX": [b"UPX0", b"UPX1"],
    "Enigma": [b".enigma"],
}
print("\npacker/protector signatures:")
found_any = False
for k, pats in sigs.items():
    hits = sum(data.count(p) for p in pats)
    if hits:
        found_any = True
        print(f"  {k}: {hits} hits")
if not found_any:
    print("  NONE found  -> looks like a PLAIN, unpacked PE (static patching is viable)")

# ---------- font-related strings ----------
print("\nfont-related strings (offset, string):")
pats = [rb"FONTES\\[A-Z_0-9]+", rb"BIG_ARABIC", rb"SMALL_FONT(_02)?", rb"BIG_FONT",
        rb"BIG_RUS", rb"DEBUG_FONT", rb"LoadFont", rb"Fonts_Z", rb"FONT\\ENGLISH"]
for p in pats:
    for m in re.finditer(p, data):
        s = m.group(0).decode("latin1", "replace")
        print(f"  0x{m.start():08X}  {s}")
