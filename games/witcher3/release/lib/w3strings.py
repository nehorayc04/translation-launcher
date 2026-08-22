#!/usr/bin/env python3
"""
w3strings.py — pure-Python READ/WRITE codec for The Witcher 3 (REDengine 3) .w3strings files.

Authoritative format reproduced from hhrhhr/Lua-utils-for-Witcher-3 (mod_w3strings.lua +
inspect_w3strings.lua) and VERIFIED byte-for-byte against the game's own files.

Layout (little-endian):
    char   magic[4]   = "RTSW"
    uint32 version    = 163 (0xA3) on the next-gen build (the rmemr tool writes 162 for back-compat)
    uint16 key1       @ off 8
    <count1 = bit6 varint @ off 10>
    block1: count1 * { uint32 str_id ^encKey ; uint32 offset (in UTF16 units) ; uint32 strlen (UTF16 chars) }
    <count2 = bit6 varint>
    block2: count2 * { uint32 key_hash (CDPR string-key hash, SAME across languages) ; uint32 str_id ^encKey }
    <count3 = bit6 varint>   (# of UTF16 units in the string blob)
    blob:   count3 * uint16  (UTF-16LE, each string \x00-terminated i.e. a trailing 0x0000)
    uint16 key2       @ end-2
    keyID = (key1<<16)|key2  -> language-key table -> encKey ("magic")

Per-string cipher (XOR): keyID 0 == CLEARTEXT (no encryption). The Arabic next-gen slot is
cleartext (key1=key2=0), so Hebrew is written as plain UTF-16LE — no key needed.

This module NEVER writes to the game. It reads bytes and returns/produces bytes.
"""
import struct

# language keyID -> (encKey, langCode)  [from mod_w3strings.lua; pre-next-gen set]
LANG_KEYS = {
    0x83496237: (0x73946816, "pl"),
    0x43975139: (0x79321793, "en"),
    0x75886138: (0x42791159, "de"),
    0x45931894: (0x12375973, "it"),
    0x23863176: (0x75921975, "fr"),
    0x24987354: (0x21793217, "cz"),
    0x18796651: (0x42387566, "es"),
    0x18632176: (0x16875467, "zh"),
    0x77932179: (0x54932186, "ru"),   # 1.0
    0x63481486: (0x42386347, "ru"),   # 1.1
    0x42378932: (0x67823218, "hu"),
    0x54834893: (0x59825646, "jp"),
    0x56328893: (0x43268768, "br"),
    0x56432683: (0x21795135, "tr"),
}


def get_key(keyid):
    if keyid == 0:
        return 0, "cleartext"
    if keyid in LANG_KEYS:
        return LANG_KEYS[keyid]
    # next-gen locales (ar / esmx / cn / kr) are not in the classic table.
    # Observed: they use keyID 0 (cleartext). Return 0 and let the caller note the unknown id.
    return 0, "unknown(%08X)->cleartext?" % keyid


class _R:
    def __init__(self, d):
        self.d = d
        self.p = 0

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v


def bit6(r):
    """Custom 6/7-bit varint (from mod_w3strings.lua)."""
    result = 0
    shift = 0
    i = 1
    while True:
        b = r.u8()
        if b == 128:
            return 0
        s = 6
        mask = 255
        if b > 127:
            mask = 127
            s = 7
        elif b > 63:
            if i == 1:
                mask = 63
        result |= (b & mask) << shift
        shift += s
        i += 1
        if (b < 64) or (i == 3 and b < 128):
            break
    return result


def emit_bit6(value):
    """Inverse of bit6 — first chunk = 6 bits (0x40 = 'more'), rest = 7 bits (0x80 = 'more').
    VERIFIED to reproduce the game's own count bytes (35->23, 76->4c01, 27601->51af03,
    2174539->4bb98902) AND to round-trip through bit6() for the full count range we use."""
    if value == 0:
        return b"\x80"
    chunk = value & 0x3F
    value >>= 6
    if value == 0:
        return bytes((chunk,))
    out = bytearray((chunk | 0x40,))
    while True:
        chunk = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(chunk)
            break
        out.append(chunk | 0x80)
    return bytes(out)


def decode(data, note_unknown=None):
    """Decode .w3strings bytes -> dict. Returns {version, keyid, lang, entries:[{str_id,key_hash,text}]}"""
    assert data[:4] == b"RTSW", "not a w3strings file"
    version = struct.unpack_from("<I", data, 4)[0]
    key1 = struct.unpack_from("<H", data, 8)[0]
    key2 = struct.unpack_from("<H", data, len(data) - 2)[0]
    keyid = (key1 << 16) | key2
    enckey, lang = get_key(keyid)
    if lang.startswith("unknown") and note_unknown is not None:
        note_unknown.append(keyid)

    r = _R(data)
    r.p = 10
    count1 = bit6(r)
    t1 = []
    for _ in range(count1):
        str_id = r.u32() ^ enckey
        offset = r.u32()
        strlen = r.u32()
        t1.append((str_id, offset, strlen))
    count2 = bit6(r)
    block2 = []          # ordered list of (key_hash, str_id) — preserved verbatim for re-encode
    t2 = {}
    for _ in range(count2):
        khash = r.u32()
        sid = r.u32() ^ enckey
        block2.append((khash, sid))
        t2[sid] = khash
    count3 = bit6(r)
    str_start = r.p

    entries = []         # ordered as block1 (== blob order)
    for (str_id, offset, strlen) in t1:
        pos = offset * 2 + str_start
        string_key = (enckey >> 8) & 0xFFFF
        buf = bytearray()
        for _j in range(strlen):
            b1 = data[pos]
            b2 = data[pos + 1]
            pos += 2
            char_key = ((strlen + 1) * string_key) & 0xFFFF
            b1 ^= char_key & 0xFF
            b2 ^= (char_key >> 8) & 0xFF
            string_key = ((string_key << 1) | (string_key >> 15)) & 0xFFFF
            buf += bytes((b1, b2))
        text = buf.decode("utf-16-le", errors="replace")
        entries.append({"str_id": str_id, "offset": offset, "strlen": strlen, "text": text})
    return {
        "version": version, "keyid": keyid, "lang": lang,
        "count1": count1, "count2": count2, "count3": count3,
        "str_start": str_start, "raw_len": len(data),
        "entries": entries, "block2": block2,
    }


def encode(entries, block2, version=163, keyid=0):
    """Build a .w3strings from ordered `entries` [{str_id, text}] and `block2` [(key_hash, str_id)].

    `keyid` selects the language cipher:
      * keyid = 0  -> CLEARTEXT (the Arabic/Hebrew slot; str_id raw, strings plain UTF-16LE).
      * keyid != 0 -> the language's XOR cipher is RE-APPLIED, exactly inverting decode(): str_id is
        XORed with encKey in BOTH blocks, and each string is enciphered with the rotating
        `string_key` stream (it is a symmetric XOR, so the same routine encrypts and decrypts).

    ⚠ Getting this wrong is SILENT and BRUTAL: writing a non-Arabic language file as cleartext makes
    the game decipher it with that language's real key -> every str_id/string turns to garbage and the
    ENTIRE UI falls back to raw keys (#PANEL_CONTINUE, #MENU_MAIN_QUIT ...). Always verify an identity
    round-trip is BYTE-IDENTICAL before writing a language file.
    """
    enckey, _lang = get_key(keyid)

    # --- strings blob (UTF-16LE, each terminated by 0x0000) + block1 offsets ---
    blob = bytearray()
    block1 = []
    for e in entries:
        u16 = e["text"].encode("utf-16-le")
        strlen = len(u16) // 2                      # UTF-16 code units, excl. terminator
        offset = len(blob) // 2                      # in UTF-16 units, into the blob
        block1.append((e["str_id"], offset, strlen))
        if enckey:
            string_key = (enckey >> 8) & 0xFFFF     # reset per string, same as decode()
            for j in range(strlen):
                b1 = u16[j * 2]
                b2 = u16[j * 2 + 1]
                char_key = ((strlen + 1) * string_key) & 0xFFFF
                b1 ^= char_key & 0xFF
                b2 ^= (char_key >> 8) & 0xFF
                string_key = ((string_key << 1) | (string_key >> 15)) & 0xFFFF
                blob += bytes((b1, b2))
        else:
            blob += u16
        blob += b"\x00\x00"                          # terminator (never enciphered — decode reads
                                                     # exactly `strlen` units and skips it)
    count3 = len(blob) // 2

    out = bytearray()
    out += b"RTSW"
    out += struct.pack("<I", version)
    out += struct.pack("<H", (keyid >> 16) & 0xFFFF)  # key1
    out += emit_bit6(len(block1))
    for (sid, off, ln) in block1:
        out += struct.pack("<III", sid ^ enckey, off, ln)
    out += emit_bit6(len(block2))
    for (kh, sid) in block2:
        out += struct.pack("<II", kh, sid ^ enckey)
    out += emit_bit6(count3)
    out += blob
    out += struct.pack("<H", keyid & 0xFFFF)          # key2
    return bytes(out)


if __name__ == "__main__":
    import sys, os
    GAME = r"D:\Games\The Witcher 3 - Complete Edition"
    targets = sys.argv[1:] or [
        os.path.join(GAME, "dlc", "dlc9", "content", "ar.w3strings"),
        os.path.join(GAME, "dlc", "dlc9", "content", "en.w3strings"),
        os.path.join(GAME, "content", "content0", "ar.w3strings"),
        os.path.join(GAME, "content", "content0", "en.w3strings"),
    ]
    for path in targets:
        with open(path, "rb") as f:
            data = f.read()
        unk = []
        d = decode(data, note_unknown=unk)
        print("=" * 70)
        print(f"{path}")
        print(f"  version={d['version']} keyid=0x{d['keyid']:08X} lang={d['lang']} "
              f"count1={d['count1']} count2={d['count2']} count3={d['count3']} bytes={d['raw_len']}")
        for e in d["entries"][:4]:
            txt = e["text"].replace("\n", "\\n")
            print(f"    id=0x{e['str_id']:08X} len={len(e['text'])} text={txt!r}")
        if len(d["entries"]) > 4:
            print(f"    ... (+{len(d['entries'])-4} more)")
