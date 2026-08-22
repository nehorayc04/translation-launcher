"""
gl_locr.py — decode Glacier LOCR (UI text) + CLNG (language list) resources for
007 First Light. Read-only groundwork tool.

Format from AnthonyFuller/TonyTools HMLanguages Languages.cpp (LOCR::Convert,
CLNG::Convert). 007 First Light uses a game-specific l10n XTEA key (from
RPKG-Tool first-light branch crypto.cpp), different from Hitman's.

LOCR v2 (H3-family) layout:
  byte 0            : u8 version (=1)
  language offset table (starts at byte 1):
    numLanguages = (offset[0] - 1) / 4
    numLanguages x u32 offset   (absolute offset into buffer; 0xFFFFFFFF = empty)
  per-language block at `offset`:
    u32 numStrings
    numStrings x { u32 lineHash ; u32 encLen ; encLen bytes (XTEA) ; u8 0x00 }
      -> decrypted bytes are UTF-8, truncated at first NUL.

CLNG: one bool (1 byte) per language slot; the byte count = number of language slots.
"""
import struct

# 007 First Light localization XTEA key (RPKG-Tool first-light crypto.cpp l10n_key)
L10N_KEY = (0x68AC3361, 0x562B4AA0, 0xB9F2771F, 0x28EB3CE7)
XTEA_DELTA = 0x9E3779B9
XTEA_ROUNDS = 32
M32 = 0xFFFFFFFF


def xtea_decrypt(data: bytes, key=L10N_KEY) -> bytes:
    buf = bytearray(data)
    n = len(buf) // 8
    for i in range(n):
        v0 = struct.unpack_from("<I", buf, i * 8)[0]
        v1 = struct.unpack_from("<I", buf, i * 8 + 4)[0]
        s = (XTEA_DELTA * XTEA_ROUNDS) & M32
        for _ in range(XTEA_ROUNDS):
            v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0 & M32) ^ ((s + key[(s >> 11) & 3]) & M32))) & M32
            s = (s - XTEA_DELTA) & M32
            v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1 & M32) ^ ((s + key[s & 3]) & M32))) & M32
        struct.pack_into("<I", buf, i * 8, v0 & M32)
        struct.pack_into("<I", buf, i * 8 + 4, v1 & M32)
    return bytes(buf)


def xtea_encrypt(s: bytes, key=L10N_KEY) -> bytes:
    data = bytearray(s)
    pad = (-len(data)) % 8
    data.extend(b"\x00" * pad)
    n = len(data) // 8
    for i in range(n):
        v0 = struct.unpack_from("<I", data, i * 8)[0]
        v1 = struct.unpack_from("<I", data, i * 8 + 4)[0]
        s2 = 0
        for _ in range(XTEA_ROUNDS):
            v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1 & M32) ^ ((s2 + key[s2 & 3]) & M32))) & M32
            s2 = (s2 + XTEA_DELTA) & M32
            v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0 & M32) ^ ((s2 + key[(s2 >> 11) & 3]) & M32))) & M32
        struct.pack_into("<I", data, i * 8, v0 & M32)
        struct.pack_into("<I", data, i * 8 + 4, v1 & M32)
    return bytes(data)


def _cstr(b: bytes) -> str:
    z = b.find(b"\x00")
    if z >= 0:
        b = b[:z]
    return b.decode("utf-8", "replace")


def decode_locr(data: bytes):
    """Return list of language blocks; each is None (empty) or list[(lineHash:int, str)]."""
    version = data[0]
    off0 = struct.unpack_from("<I", data, 1)[0]
    num_langs = (off0 - 1) // 4
    offsets = [struct.unpack_from("<I", data, 1 + 4 * i)[0] for i in range(num_langs)]
    langs = []
    for off in offsets:
        if off == 0xFFFFFFFF:
            langs.append(None)
            continue
        pos = off
        num_strings = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        entries = []
        for _ in range(num_strings):
            line_hash = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            enc_len = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            enc = data[pos:pos + enc_len]
            pos += enc_len
            s = _cstr(xtea_decrypt(enc))
            pos += 1  # trailing null
            entries.append((line_hash, s))
        langs.append(entries)
    return version, langs


def encode_locr(langs, version=1) -> bytes:
    """Rebuild a LOCR resource from decode_locr output.
    langs = list of (None | list[(lineHash:int, str)]); mirrors TonyTools LOCR::Rebuild (v2).
    NOTE: not byte-identical to the game (string ORDER within a language is preserved, but the
    offset table + our XTEA padding reproduce a valid resource the engine reads)."""
    num = len(langs)
    out = bytearray()
    out.append(version & 0xFF)              # v2 version byte
    table_pos = len(out)                     # offset table starts here (byte 1)
    out += b"\x00" * (num * 4)               # reserve offset table
    for i, block in enumerate(langs):
        if not block:
            struct.pack_into("<I", out, table_pos + i * 4, 0xFFFFFFFF)
            continue
        struct.pack_into("<I", out, table_pos + i * 4, len(out))
        out += struct.pack("<I", len(block))
        for line_hash, s in block:
            enc = xtea_encrypt(s.encode("utf-8"))
            out += struct.pack("<I", line_hash & 0xFFFFFFFF)
            out += struct.pack("<I", len(enc))
            out += enc
            out += b"\x00"
    return bytes(out)


def decode_clng(data: bytes):
    """Return list[bool], one per language slot."""
    return [bool(b) for b in data]


def _cli():
    import argparse, sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from gl_rpkg import RPKG
    ap = argparse.ArgumentParser()
    ap.add_argument("rpkg")
    ap.add_argument("cmd", choices=["clng", "locr", "locrsample"])
    ap.add_argument("arg", nargs="?", default="")
    a = ap.parse_args()
    r = RPKG(a.rpkg)
    if a.cmd == "clng":
        i = r.indices("CLNG")[0]
        data = r.read(i)
        print("CLNG raw:", data.hex(" "), "  slots:", decode_clng(data))
    elif a.cmd == "locr":
        i = int(a.arg)
        data = r.read(i)
        ver, langs = decode_locr(data)
        print(f"LOCR {r.resources[i].name()}  version={ver}  languages={len(langs)}")
        for li, block in enumerate(langs):
            n = 0 if block is None else len(block)
            print(f"  lang[{li}]: {'EMPTY' if block is None else str(n)+' strings'}")
            if block:
                for h, s in block[:4]:
                    print(f"      {h:08X}: {s!r}")
    elif a.cmd == "locrsample":
        # decode the first LOCR that has content and show per-language first string
        idxs = r.indices("LOCR")
        big = sorted(idxs, key=lambda i: -r.resources[i].size_final)[:3]
        for i in big:
            data = r.read(i)
            ver, langs = decode_locr(data)
            counts = [0 if b is None else len(b) for b in langs]
            print(f"\nLOCR {r.resources[i].name()} final={r.resources[i].size_final} "
                  f"langs={len(langs)} counts={counts}")
            for li, block in enumerate(langs):
                if block:
                    s = block[0][1]
                    print(f"   [{li}] {s!r}")


if __name__ == "__main__":
    _cli()
