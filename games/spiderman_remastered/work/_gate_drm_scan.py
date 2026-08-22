"""MSMR Phase-1 DRM / integrity screen. READ-ONLY on the game folder.

Scans a PE for packer/DRM markers and integrity-check strings, in BOTH
UTF-8 and UTF-16LE, with EXACT occurrence counts (not ripgrep line counts),
and dumps the PE section table + per-section entropy.

Usage:  python _gate_drm_scan.py <exe-or-dll> [more...]
"""
from __future__ import annotations
import math, mmap, os, re, struct, sys

# ---- the needles, grouped -------------------------------------------------
PACKER = ["Denuvo", "denuvo", "DENUVO", "VMProtect", "vmprotect", ".vmp0",
          ".vmp1", ".vmp2", ".xtls", "Themida", "WinLicense", "UPX0", "UPX1",
          "Enigma", "ASProtect", "SecuROM", "SafeDisc", "Arxan"]
ANTICHEAT = ["EasyAntiCheat", "easyanticheat", "EAC_", "BattlEye", "BEClient",
             "BEService", "battleye", "Denuvo Anti-Cheat", "nProtect",
             "GameGuard", "Vanguard", "vgk.sys"]
INTEGRITY = ["SHA256", "sha256", "Sha256", "SHA-256", "sha_256", "SHA512",
             "sha1", "SHA1", "integrity", "Integrity", "INTEGRITY",
             "tamper", "Tamper", "TAMPER", "checksum", "Checksum", "CHECKSUM",
             "CRC32", "crc32", "md5", "MD5", "signature", "Signature",
             "SIGNATURE", "verifyfile", "VerifyFile", "WinVerifyTrust",
             "BCryptHash", "CryptAcquireContext", "hash_mismatch",
             "HashMismatch", "corrupt", "Corrupt"]


def entropy(b: bytes) -> float:
    if not b:
        return 0.0
    hist = [0] * 256
    for x in b:
        hist[x] += 1
    n = len(b)
    e = 0.0
    for c in hist:
        if c:
            p = c / n
            e -= p * math.log2(p)
    return e


def count_all(mm, needles):
    """exact occurrence counts, utf-8 and utf-16le, non-overlapping."""
    out = {}
    for s in needles:
        a = len(re.findall(re.escape(s.encode("utf-8")), mm))
        w = len(re.findall(re.escape(s.encode("utf-16-le")), mm))
        if a or w:
            out[s] = (a, w)
    return out


def pe_sections(data: bytes):
    if data[:2] != b"MZ":
        return None, "not an MZ image"
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return None, "no PE signature"
    coff = e_lfanew + 4
    machine, nsec, _tds, _pst, _nsym, opt_sz, chars = struct.unpack_from(
        "<HHIIIHH", data, coff)
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    pe32p = magic == 0x20B
    entry = struct.unpack_from("<I", data, opt + 16)[0]
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
    dll_chars = struct.unpack_from("<H", data, opt + (70 if pe32p else 70))[0]
    sec_off = opt + opt_sz
    secs = []
    for i in range(nsec):
        o = sec_off + i * 40
        name = data[o:o + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
        c = struct.unpack_from("<I", data, o + 36)[0]
        secs.append(dict(name=name, vsize=vsize, vaddr=vaddr, rsize=rsize,
                         raddr=raddr, chars=c))
    return dict(machine=machine, nsec=nsec, magic=magic, entry=entry,
                size_of_image=size_of_image, dll_chars=dll_chars,
                secs=secs, coff_chars=chars), None


def flagstr(c):
    f = []
    if c & 0x20000000: f.append("EXEC")
    if c & 0x40000000: f.append("READ")
    if c & 0x80000000: f.append("WRITE")
    if c & 0x00000020: f.append("CODE")
    if c & 0x00000040: f.append("IDATA")
    if c & 0x00000080: f.append("UDATA")
    if c & 0x02000000: f.append("DISCARD")
    return "|".join(f)


def scan(path):
    print("=" * 78)
    print(f"FILE: {path}")
    sz = os.path.getsize(path)
    print(f"SIZE: {sz:,} bytes")
    with open(path, "rb") as f:
        data = f.read()

    pe, err = pe_sections(data)
    if err:
        print(f"  PE parse: {err}")
    else:
        print(f"  machine=0x{pe['machine']:04X} magic=0x{pe['magic']:03X} "
              f"sections={pe['nsec']} SizeOfImage={pe['size_of_image']:,} "
              f"EntryRVA=0x{pe['entry']:X}")
        print(f"  {'name':<10}{'VirtSize':>13}{'RawSize':>13}{'VAddr':>11}  flags   entropy")
        ep = pe["entry"]
        for s in pe["secs"]:
            body = data[s["raddr"]:s["raddr"] + min(s["rsize"], 4 << 20)]
            ent = entropy(body)
            mark = "  <== ENTRY" if s["vaddr"] <= ep < s["vaddr"] + max(s["vsize"], 1) else ""
            print(f"  {s['name']:<10}{s['vsize']:>13,}{s['rsize']:>13,}"
                  f"{s['vaddr']:>11X}  {flagstr(s['chars']):<28}{ent:5.2f}{mark}")
        reloc = [s for s in pe["secs"] if s["name"] == ".reloc"]
        if reloc:
            r = reloc[0]["vsize"]
            print(f"  .reloc = {r:,} B  ({r / pe['size_of_image'] * 100:.3f}% of image) "
                  f"-> {'TINY (packed?)' if r / pe['size_of_image'] < 0.0005 else 'normal, unpacked'}")
        else:
            print("  .reloc = ABSENT")

    with open(path, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        for label, needles in (("PACKER/DRM", PACKER), ("ANTI-CHEAT", ANTICHEAT),
                               ("INTEGRITY", INTEGRITY)):
            hits = count_all(mm, needles)
            print(f"  --- {label} --- ", end="")
            if not hits:
                print("NONE (0 hits, utf-8 and utf-16le)")
            else:
                print()
                for k, (a, w) in sorted(hits.items(), key=lambda x: -(x[1][0] + x[1][1])):
                    print(f"      {k:<24} utf8={a:<6} utf16le={w}")
        mm.close()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        scan(p)
