# -*- coding: utf-8 -*-
"""Recover the game's name->oid hash (CRC64 variant) from the exe and VERIFY it against a
known Fonts_Z oid (BIG_ARABIC = 0xAFBE3792DDA3B358). If it matches, we can compute the oid of
ANY named object (e.g. the subtitle text styles) and go find it in the DPCs.

Algorithm recovered from 0x14006BF80:
    rax = seed
    for each char c in name:
        idx  = bytetab[c] ^ (rax >> 56)
        rax  = ((rax << 8) & 0xFFFFFFFFFFFFFFFF) ^ qtab[idx]
"""
import struct

EXE = r"D:\Games\A Plague Tale - Requiem\APlagueTaleRequiem_x64.exe"
data = open(EXE, "rb").read()

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

def va2off(va):
    r = va - IMGBASE
    for nm, vaddr, vs, ra, rs in SECS:
        if vaddr <= r < vaddr + max(vs, rs):
            return ra + (r - vaddr)
    return None

BYTETAB_VA = IMGBASE + 0x1879B00
QTAB_VA = IMGBASE + 0x1879C00
SEED_VA = 0x141A23D40           # from: mov rax,[rip+0x19b7db9] @ 0x14006BF80 (next=0x14006BF87)

bt_off = va2off(BYTETAB_VA)
qt_off = va2off(QTAB_VA)
sd_off = va2off(SEED_VA)
print(f"bytetab off=0x{bt_off:08X}  qtab off=0x{qt_off:08X}  seed off=0x{sd_off:08X}")

bytetab = list(data[bt_off:bt_off + 256])
qtab = list(struct.unpack_from("<256Q", data, qt_off))
seed = struct.unpack_from("<Q", data, sd_off)[0]
print(f"seed = 0x{seed:016X}")
print(f"bytetab[0:16] = {bytetab[:16]}")
print(f"qtab[0:4] = {[hex(x) for x in qtab[:4]]}")

M = (1 << 64) - 1

def name_hash(s: str, seed_val: int) -> int:
    h = seed_val
    for ch in s.encode("latin1"):
        idx = bytetab[ch] ^ ((h >> 56) & 0xFF)
        h = ((h << 8) & M) ^ qtab[idx]
    return h

KNOWN = {
    "BIG_ARABIC": 0xAFBE3792DDA3B358,
}
print("\n=== verify against known Fonts_Z oids ===")
ok = False
for nm, want in KNOWN.items():
    got = name_hash(nm, seed)
    hit = "MATCH" if got == want else "no"
    print(f"  {nm:12} want=0x{want:016X} got=0x{got:016X}  {hit}")
    ok |= (got == want)

if not ok:
    # try seed=0 and seed=~0 as fallbacks, and try uppercase/lowercase variants
    print("\n  (seed from the global didn't match — trying alternates)")
    for sname, sv in [("0", 0), ("~0", M)]:
        for variant in ("BIG_ARABIC", "big_arabic", "FONTES\\BIG_ARABIC"):
            g = name_hash(variant, sv)
            if g == 0xAFBE3792DDA3B358:
                print(f"  MATCH with seed={sname} variant={variant!r}")
                ok = True
if ok:
    print("\n=== oids of the subtitle text styles ===")
    for nm in ["text_PLGSubtitle_Small", "text_PLGSubtitle_Medium", "text_PLGSubtitle_Large",
               "text_PLGSubtitleSpeaker_Small", "BIG_FONT", "SMALL_FONT"]:
        print(f"  {nm:32} -> 0x{name_hash(nm, seed):016X}")
