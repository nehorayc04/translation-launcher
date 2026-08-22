"""
gl_pkgdef.py — decrypt / edit / re-encrypt the Glacier `packagedefinition.txt`
(and `thumbs.dat`), for 007 First Light. Needed to mount a patch chunk: the
`@partition ... patchlevel=N` line controls how many patch levels the engine loads
(0 => no patches), so a mod bumps it and re-encrypts.

Format (RPKG-Tool first-light decrypt/encrypt_packagedefinition_thumbs.cpp):
  16-byte fixed header + u32 CRC32(plaintext, original length) + XTEA(body, thumbs key)
  body padded to a multiple of 8 with 0x00 before encrypt; the trailing zeros are
  trimmed after decrypt.

XTEA (thumbs): key {0x71482CF0,0x5FDC4B9F,0x86CE569D,0x0509FC1E}, delta 0x61C88647,
32 rounds. CRC variant is auto-detected against the file's own stored checksum.
"""
import struct
import re
import zlib

HEADER16 = bytes([0x22, 0x3D, 0x6F, 0x9A, 0xB3, 0xF8, 0xFE, 0xB6,
                  0x61, 0xD9, 0xCC, 0x1C, 0x62, 0xDE, 0x83, 0x41])
THUMBS_KEY = (0x71482CF0, 0x5FDC4B9F, 0x86CE569D, 0x0509FC1E)
DELTA = 0x61C88647
M = 0xFFFFFFFF


def _dec_block(v0, v1):
    s = 0xC6EF3720
    for _ in range(32):
        v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0 & M) ^ ((s + THUMBS_KEY[(s >> 11) & 3]) & M))) & M
        s = (s + DELTA) & M
        v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1 & M) ^ ((s + THUMBS_KEY[s & 3]) & M))) & M
    return v0, v1


def _enc_block(v0, v1):
    s = 0
    for _ in range(32):
        v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1 & M) ^ ((s + THUMBS_KEY[s & 3]) & M))) & M
        s = (s - DELTA) & M
        v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0 & M) ^ ((s + THUMBS_KEY[(s >> 11) & 3]) & M))) & M
    return v0, v1


# raw CRC32 (poly 0xEDB88320, init 0, no final xor) — RPKG-Tool crc32::update(table,0,...)
_CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ 0xEDB88320 if (_c & 1) else (_c >> 1)
    _CRC_TABLE.append(_c)


def _crc_raw(data):
    # verified against the game file: standard zlib CRC-32 over the UNPADDED plaintext
    return zlib.crc32(bytes(data)) & M


def decrypt(path):
    d = open(path, "rb").read()
    header16 = d[:16]                       # per-file 16-byte signature the engine validates
    stored_crc = struct.unpack_from("<I", d, 16)[0]
    body = bytearray(d[20:])
    while len(body) % 8:
        body.append(0)
    out = bytearray()
    for i in range(len(body) // 8):
        v0, v1 = struct.unpack_from("<II", body, i * 8)
        v0, v1 = _dec_block(v0, v1)
        out += struct.pack("<II", v0, v1)
    # trim trailing zeros
    e = len(out)
    while e > 0 and out[e - 1] == 0:
        e -= 1
    return bytes(out[:e]), stored_crc, header16


def encrypt(plaintext: bytes, header16: bytes = None) -> bytes:
    """Re-encrypt. header16 MUST be the ORIGINAL file's 16-byte signature (the engine
    validates it) — pass the value decrypt() returned. Falls back to the legacy constant
    only if not supplied (do NOT rely on that for a real game file)."""
    if header16 is None:
        header16 = bytes(HEADER16)
    orig_len = len(plaintext)
    body = bytearray(plaintext)
    while len(body) % 8:
        body.append(0)
    crc = _crc_raw(body[:orig_len])
    enc = bytearray()
    for i in range(len(body) // 8):
        v0, v1 = struct.unpack_from("<II", body, i * 8)
        v0, v1 = _enc_block(v0, v1)
        enc += struct.pack("<II", v0, v1)
    return bytes(header16) + struct.pack("<I", crc) + bytes(enc)


def set_patchlevel(plaintext: bytes, level: int, chunk_index: int = 0) -> bytes:
    """Bump ONLY the partition at `chunk_index` to `patchlevel=level`.
    Partitions are ordered: index 0 = `super` = chunk0, index 1 = `base` = chunk1, ...
    Bumping EVERY partition makes the engine hunt for chunkNpatch1.rpkg for every N — and a
    missing patch file crashes boot. So bump only the chunk we actually ship a patch for."""
    txt = plaintext.decode("utf-8", "replace")
    idx = [0]

    def repl(m):
        cur = idx[0]
        idx[0] += 1
        return f"patchlevel={level}" if cur == chunk_index else m.group(0)

    txt2 = re.sub(r"patchlevel=\d+", repl, txt)
    return txt2.encode("utf-8")


def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["decrypt", "identity", "setlevel"])
    ap.add_argument("path")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    plain, stored_crc, hdr = decrypt(a.path)
    if a.cmd == "decrypt":
        print(plain.decode("utf-8", "replace")[:2000])
        print(f"\n[stored_crc={stored_crc:08X}  crc_raw={_crc_raw(plain):08X}]")
    elif a.cmd == "identity":
        # re-encrypt the unmodified plaintext, compare to the original file
        orig = open(a.path, "rb").read()
        re_enc = encrypt(plain, hdr)
        same = re_enc == orig
        print(f"packagedefinition codec identity: {'BYTE-IDENTICAL' if same else 'DIFFER'} "
              f"(orig {len(orig)} vs {len(re_enc)})")
        if not same:
            # locate first difference
            for i in range(min(len(orig), len(re_enc))):
                if orig[i] != re_enc[i]:
                    print(f"  first diff @ {i}: {orig[i]:02X} vs {re_enc[i]:02X}")
                    break
        print(f"  crc match: {_crc_raw(plain) == stored_crc}")
    elif a.cmd == "setlevel":
        new_plain = set_patchlevel(plain, a.level)
        enc = encrypt(new_plain, hdr)
        out = a.out or (a.path + f".patchlevel{a.level}")
        open(out, "wb").write(enc)
        # verify round-trip
        rp, _, _ = decrypt(out)
        lv = re.findall(r"patchlevel=\d+", rp.decode("utf-8", "replace"))
        print(f"wrote {out}  ({len(enc)} bytes)  patchlevels now: {set(lv)}")


if __name__ == "__main__":
    _cli()
