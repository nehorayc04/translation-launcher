"""Dump PE imports + security-directory state. READ-ONLY.
If the exe never imports wintrust/bcrypt/crypt32, a lone 'WinVerifyTrust'
string is dead weight, not a live verification path."""
import struct, sys

CRYPTO = ("wintrust", "bcrypt", "crypt32", "advapi32", "ncrypt", "cryptsp",
          "cryptbase", "secur32")


def rva2off(secs, rva):
    for s in secs:
        if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["rsize"]):
            return s["raddr"] + (rva - s["vaddr"])
    return None


def main(path):
    data = open(path, "rb").read()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    coff = e + 4
    nsec, opt_sz = struct.unpack_from("<H", data, coff + 2)[0], struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    pe32p = magic == 0x20B
    ddir = opt + (112 if pe32p else 96)
    nrva = struct.unpack_from("<I", data, opt + (108 if pe32p else 92))[0]
    sec_off = opt + opt_sz
    secs = []
    for i in range(nsec):
        o = sec_off + i * 40
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
        secs.append(dict(vaddr=vaddr, vsize=vsize, rsize=rsize, raddr=raddr))

    # data dir 4 = certificate (file OFFSET, not RVA), 1 = import
    cert_rva, cert_sz = struct.unpack_from("<II", data, ddir + 4 * 8)
    imp_rva, imp_sz = struct.unpack_from("<II", data, ddir + 1 * 8)
    print(f"NumberOfRvaAndSizes={nrva}")
    print(f"CERTIFICATE dir: offset=0x{cert_rva:X} size={cert_sz:,} "
          f"-> {'AUTHENTICODE PRESENT' if cert_sz else 'NO EMBEDDED SIGNATURE'}")

    off = rva2off(secs, imp_rva)
    names = []
    if off:
        i = 0
        while True:
            ent = off + i * 20
            oft, tds, fc, nrva_, fthunk = struct.unpack_from("<IIIII", data, ent)
            if not (oft or nrva_ or fthunk):
                break
            no = rva2off(secs, nrva_)
            if no is None:
                break
            end = data.index(b"\0", no)
            names.append(data[no:end].decode("latin1"))
            i += 1
    print(f"IMPORTED DLLs ({len(names)}):")
    for n in sorted(names, key=str.lower):
        flag = "   <== CRYPTO/TRUST" if any(c in n.lower() for c in CRYPTO) else ""
        print(f"   {n}{flag}")


if __name__ == "__main__":
    main(sys.argv[1])
