"""Crimson Desert (Pearl Abyss "BlackSpace" engine) container codec.

Pure Python. Ported from the community reference implementations
(read-only ports, adapted/verified against the real shipped files):
  - MrIkso/CrimsonDesertTools (C#)      - container/crypto research
  - lazorr410/crimson-desert-unpacker   - PAZ_DECRYPTION.md (ChaCha20 key derivation)
  - hzeemr/crimsonforge (Python)        - pamt/papgt/paloc/checksum/crypto/compression
    engines, matured through several game patches (April-2026 renames etc.)

Formats:
  .pamt  - per-package archive index (dir trie + file-name trie + file records)
  .paz   - the raw/compressed/encrypted data blob(s) for a package
  .papgt - meta/0.papgt, the root package-group table (maps a numbered
           folder like 0020/ to a language bitmask + expected PAMT checksum)
  .paloc - the actual localization string table (flat length-prefixed
           UTF-8 strings, decrypted+decompressed .paloc payload)

Verified round-trip against games/crimson_desert install (2026-08-07):
  0020/0.pamt -> localizationstring_eng.paloc entry decrypts + decompresses
  cleanly to a real English string table.
"""
from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass, field
from typing import Optional

import lz4.block
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

MASK32 = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# PaChecksum (Pearl Abyss Bob-Jenkins lookup3 variant) - used for integrity
# fields (pamt self-crc, papgt self-crc, paz crc). NOT the encryption key.
# ---------------------------------------------------------------------------
PA_MAGIC = 0x2145E233


def _rol(x: int, k: int) -> int:
    return ((x << k) | (x >> (32 - k))) & MASK32


def _ror(x: int, k: int) -> int:
    return ((x >> k) | (x << (32 - k))) & MASK32


def pa_checksum(data: bytes) -> int:
    length = len(data)
    if length == 0:
        return 0
    a = b = c = (length - PA_MAGIC) & MASK32
    off = 0
    remaining = length
    while remaining > 12:
        a = (a + struct.unpack_from("<I", data, off)[0]) & MASK32
        b = (b + struct.unpack_from("<I", data, off + 4)[0]) & MASK32
        c = (c + struct.unpack_from("<I", data, off + 8)[0]) & MASK32
        a = (a - c) & MASK32; a ^= _rol(c, 4);  c = (c + b) & MASK32
        b = (b - a) & MASK32; b ^= _rol(a, 6);  a = (a + c) & MASK32
        c = (c - b) & MASK32; c ^= _rol(b, 8);  b = (b + a) & MASK32
        a = (a - c) & MASK32; a ^= _rol(c, 16); c = (c + b) & MASK32
        b = (b - a) & MASK32; b ^= _rol(a, 19); a = (a + c) & MASK32
        c = (c - b) & MASK32; c ^= _rol(b, 4);  b = (b + a) & MASK32
        off += 12
        remaining -= 12

    if remaining >= 12: c = (c + (data[off + 11] << 24)) & MASK32
    if remaining >= 11: c = (c + (data[off + 10] << 16)) & MASK32
    if remaining >= 10: c = (c + (data[off + 9] << 8)) & MASK32
    if remaining >= 9:  c = (c + data[off + 8]) & MASK32
    if remaining >= 8:  b = (b + (data[off + 7] << 24)) & MASK32
    if remaining >= 7:  b = (b + (data[off + 6] << 16)) & MASK32
    if remaining >= 6:  b = (b + (data[off + 5] << 8)) & MASK32
    if remaining >= 5:  b = (b + data[off + 4]) & MASK32
    if remaining >= 4:  a = (a + (data[off + 3] << 24)) & MASK32
    if remaining >= 3:  a = (a + (data[off + 2] << 16)) & MASK32
    if remaining >= 2:  a = (a + (data[off + 1] << 8)) & MASK32
    if remaining >= 1:  a = (a + data[off]) & MASK32

    v82 = ((b ^ c) - _rol(b, 14)) & MASK32
    v83 = ((a ^ v82) - _rol(v82, 11)) & MASK32
    v84 = ((v83 ^ b) - _ror(v83, 7)) & MASK32
    v85 = ((v84 ^ v82) - _rol(v84, 16)) & MASK32
    v86 = _rol(v85, 4)
    t = ((v83 ^ v85) - v86) & MASK32
    v87 = ((t ^ v84) - _rol(t, 14)) & MASK32
    return ((v87 ^ v85) - _ror(v87, 8)) & MASK32


# ---------------------------------------------------------------------------
# ChaCha20 key derivation (deterministic, filename-only, no key database)
# ---------------------------------------------------------------------------
HASH_INITVAL = 0x000C5EDE
IV_XOR = 0x60616263
XOR_DELTAS = [
    0x00000000, 0x0A0A0A0A, 0x0C0C0C0C, 0x06060606,
    0x0E0E0E0E, 0x0A0A0A0A, 0x06060606, 0x02020202,
]


def _hashlittle(data: bytes, initval: int = 0) -> int:
    """Bob Jenkins' lookup3 hashlittle - standard variant (key derivation)."""
    length = len(data)
    a = b = c = (0xDEADBEEF + length + initval) & MASK32
    off = 0
    remaining = length
    while remaining > 12:
        a = (a + struct.unpack_from("<I", data, off)[0]) & MASK32
        b = (b + struct.unpack_from("<I", data, off + 4)[0]) & MASK32
        c = (c + struct.unpack_from("<I", data, off + 8)[0]) & MASK32
        a = (a - c) & MASK32; a ^= _rol(c, 4);  c = (c + b) & MASK32
        b = (b - a) & MASK32; b ^= _rol(a, 6);  a = (a + c) & MASK32
        c = (c - b) & MASK32; c ^= _rol(b, 8);  b = (b + a) & MASK32
        a = (a - c) & MASK32; a ^= _rol(c, 16); c = (c + b) & MASK32
        b = (b - a) & MASK32; b ^= _rol(a, 19); a = (a + c) & MASK32
        c = (c - b) & MASK32; c ^= _rol(b, 4);  b = (b + a) & MASK32
        off += 12
        remaining -= 12

    tail = data[off:] + b"\x00" * 12
    if remaining >= 12:
        c = (c + struct.unpack_from("<I", tail, 8)[0]) & MASK32
    elif remaining >= 9:
        v = struct.unpack_from("<I", tail, 8)[0]
        c = (c + (v & (MASK32 >> (8 * (12 - remaining))))) & MASK32
    if remaining >= 8:
        b = (b + struct.unpack_from("<I", tail, 4)[0]) & MASK32
    elif remaining >= 5:
        v = struct.unpack_from("<I", tail, 4)[0]
        b = (b + (v & (MASK32 >> (8 * (8 - remaining))))) & MASK32
    if remaining >= 4:
        a = (a + struct.unpack_from("<I", tail, 0)[0]) & MASK32
    elif remaining >= 1:
        v = struct.unpack_from("<I", tail, 0)[0]
        a = (a + (v & (MASK32 >> (8 * (4 - remaining))))) & MASK32
    elif remaining == 0:
        return c

    c ^= b; c = (c - _rol(b, 14)) & MASK32
    a ^= c; a = (a - _rol(c, 11)) & MASK32
    b ^= a; b = (b - _rol(a, 25)) & MASK32
    c ^= b; c = (c - _rol(b, 16)) & MASK32
    a ^= c; a = (a - _rol(c, 4)) & MASK32
    b ^= a; b = (b - _rol(a, 14)) & MASK32
    c ^= b; c = (c - _rol(b, 24)) & MASK32
    return c


def derive_key_iv(filename: str) -> tuple[bytes, bytes]:
    """Derive the 32-byte ChaCha20 key + 16-byte IV from a filename alone."""
    basename = os.path.basename(filename).lower()
    seed = _hashlittle(basename.encode("utf-8"), HASH_INITVAL)
    iv = struct.pack("<I", seed) * 4
    key_base = seed ^ IV_XOR
    key = b"".join(struct.pack("<I", key_base ^ d) for d in XOR_DELTAS)
    return key, iv


def chacha20_crypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Symmetric ChaCha20 (encrypt == decrypt with the same key/iv)."""
    cipher = Cipher(algorithms.ChaCha20(key, iv), mode=None)
    return cipher.encryptor().update(data)


def decrypt(data: bytes, filename: str) -> bytes:
    key, iv = derive_key_iv(filename)
    return chacha20_crypt(data, key, iv)


def encrypt(data: bytes, filename: str) -> bytes:
    return decrypt(data, filename)  # symmetric


# ---------------------------------------------------------------------------
# Compression (PAMT flag nibble: (flags>>16)&0xF -> 0 none, 2 lz4, 3 custom, 4 zlib)
# ---------------------------------------------------------------------------
COMP_NONE = 0
COMP_RAW = 1
COMP_LZ4 = 2
COMP_CUSTOM = 3
COMP_ZLIB = 4


def decompress(data: bytes, original_size: int, compression_type: int) -> bytes:
    if compression_type == COMP_NONE:
        return data
    if compression_type == COMP_LZ4:
        result = lz4.block.decompress(data, uncompressed_size=original_size)
        if len(result) != original_size:
            raise ValueError(f"LZ4 size mismatch: got {len(result)}, expected {original_size}")
        return result
    if compression_type == COMP_ZLIB:
        return zlib.decompress(data)
    raise ValueError(f"Unsupported/unhandled compression type: {compression_type}")


# ---------------------------------------------------------------------------
# .pamt reader
# ---------------------------------------------------------------------------
@dataclass
class PazTableEntry:
    index: int
    checksum: int
    size: int
    entry_offset: int


@dataclass
class PamtFileEntry:
    path: str
    paz_file: str
    offset: int
    comp_size: int
    orig_size: int
    flags: int
    paz_index: int
    record_offset: int = 0

    @property
    def compression_type(self) -> int:
        return (self.flags >> 16) & 0x0F

    ENCRYPTED_EXTS = (
        ".xml", ".paloc", ".css", ".html", ".thtml", ".pami",
        ".uianiminit", ".spline2d", ".spline", ".mi", ".txt",
        ".app_xml", ".pac_xml", ".prefabdata_xml",
    )

    @property
    def encrypted(self) -> bool:
        ext = os.path.splitext(self.path.lower())[1]
        return ext in self.ENCRYPTED_EXTS


@dataclass
class PamtData:
    path: str
    self_crc: int
    paz_count: int
    paz_table: list[PazTableEntry]
    file_entries: list[PamtFileEntry]
    folder_prefix: str = ""
    raw_data: bytes = field(default=b"", repr=False)


def parse_pamt(pamt_path: str, paz_dir: Optional[str] = None) -> PamtData:
    with open(pamt_path, "rb") as f:
        data = f.read()
    if paz_dir is None:
        paz_dir = os.path.dirname(pamt_path) or "."
    pamt_stem = os.path.splitext(os.path.basename(pamt_path))[0]

    off = 0
    self_crc = struct.unpack_from("<I", data, off)[0]; off += 4
    paz_count = struct.unpack_from("<I", data, off)[0]; off += 4
    off += 8  # hash + zero

    paz_table = []
    for i in range(paz_count):
        entry_offset = off
        paz_hash = struct.unpack_from("<I", data, off)[0]; off += 4
        paz_size = struct.unpack_from("<I", data, off)[0]; off += 4
        paz_table.append(PazTableEntry(i, paz_hash, paz_size, entry_offset))
        if i < paz_count - 1:
            off += 4  # separator (index of next paz)

    folder_size = struct.unpack_from("<I", data, off)[0]; off += 4
    folder_end = off + folder_size
    folder_prefix = ""
    while off < folder_end:
        parent = struct.unpack_from("<I", data, off)[0]
        slen = data[off + 4]
        name = data[off + 5:off + 5 + slen].decode("utf-8", errors="replace")
        if parent == 0xFFFFFFFF:
            folder_prefix = name
        off += 5 + slen

    node_size = struct.unpack_from("<I", data, off)[0]; off += 4
    node_start = off
    nodes: dict[int, tuple[int, str]] = {}
    while off < node_start + node_size:
        rel = off - node_start
        parent = struct.unpack_from("<I", data, off)[0]
        slen = data[off + 4]
        name = data[off + 5:off + 5 + slen].decode("utf-8", errors="replace")
        nodes[rel] = (parent, name)
        off += 5 + slen

    def build_path(node_ref: int) -> str:
        parts = []
        cur = node_ref
        depth = 0
        while cur != 0xFFFFFFFF and depth < 64:
            if cur not in nodes:
                break
            p, n = nodes[cur]
            parts.append(n)
            cur = p
            depth += 1
        return "".join(reversed(parts))

    folder_count = struct.unpack_from("<I", data, off)[0]; off += 4
    off += 4  # hash
    off += folder_count * 16

    entries = []
    while off + 20 <= len(data):
        record_offset = off
        node_ref, paz_offset, comp_size, orig_size, flags = struct.unpack_from("<IIIII", data, off)
        off += 20
        paz_index = flags & 0xFF
        node_path = build_path(node_ref)
        full_path = f"{folder_prefix}/{node_path}" if folder_prefix else node_path
        paz_num = int(pamt_stem) + paz_index
        paz_file = os.path.join(paz_dir, f"{paz_num}.paz")
        entries.append(PamtFileEntry(
            path=full_path, paz_file=paz_file, offset=paz_offset,
            comp_size=comp_size, orig_size=orig_size, flags=flags,
            paz_index=paz_index, record_offset=record_offset,
        ))

    return PamtData(
        path=pamt_path, self_crc=self_crc, paz_count=paz_count,
        paz_table=paz_table, file_entries=entries,
        folder_prefix=folder_prefix, raw_data=data,
    )


def read_file(entry: PamtFileEntry) -> bytes:
    """Read + decrypt + decompress one file described by a PamtFileEntry."""
    with open(entry.paz_file, "rb") as f:
        f.seek(entry.offset)
        raw = f.read(entry.comp_size)
    if entry.encrypted:
        raw = decrypt(raw, entry.path)
    return decompress(raw, entry.orig_size, entry.compression_type)


# ---------------------------------------------------------------------------
# .paloc string table (already decrypted+decompressed bytes in, out)
# ---------------------------------------------------------------------------
_U32 = struct.Struct("<I")
_U32SZ = 4
_MAX_STR_LEN = 50_000_000


@dataclass
class PalocEntry:
    key: str
    value: str
    key_offset: int
    value_offset: int


def _scan_strings_fast(data: bytes) -> list[tuple[int, int, str]]:
    data_len = len(data)
    strings = []
    off = _U32SZ
    while off + _U32SZ <= data_len:
        slen = _U32.unpack_from(data, off)[0]
        if slen > _MAX_STR_LEN or off + _U32SZ + slen > data_len:
            off += _U32SZ
            continue
        if slen == 0:
            strings.append((off, 0, ""))
            off += _U32SZ
            continue
        start = off + _U32SZ
        chunk = data[start:start + slen]
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            off += _U32SZ
            continue
        has_control = any(b < 0x09 or 0x0E <= b <= 0x1F for b in chunk)
        if has_control:
            off += _U32SZ
            continue
        strings.append((off, slen, text))
        off += _U32SZ + slen
    return strings


def _is_symbolic_key(text: str) -> bool:
    if not text or len(text) > 200:
        return False
    first = text[0]
    if not (first.isascii() and (first.isalpha() or first == "_")):
        return False
    for ch in text:
        if not (ch.isascii() and (ch.isalnum() or ch in "_.-")):
            return False
    return True


def parse_paloc(data: bytes) -> list[PalocEntry]:
    if len(data) < _U32SZ:
        return []
    all_strings = _scan_strings_fast(data)
    entries: list[PalocEntry] = []
    i = 0
    count = len(all_strings)
    while i < count:
        s_off, s_len, s_text = all_strings[i]
        if s_len == 0 and i + 2 < count:
            id_off, id_len, id_text = all_strings[i + 1]
            val_off, val_len, val_text = all_strings[i + 2]
            if id_len > 0 and id_text and id_text[0].isdigit():
                entries.append(PalocEntry(id_text, val_text, id_off, val_off))
                i += 3
                continue
        if s_len > 0 and _is_symbolic_key(s_text) and i + 1 < count:
            val_off, val_len, val_text = all_strings[i + 1]
            entries.append(PalocEntry(s_text, val_text, s_off, val_off))
            i += 2
            continue
        i += 1
    return entries


def splice_values_in_raw(raw_data: bytes, replacements: list[tuple[PalocEntry, str]]) -> bytes:
    """Apply many value replacements in one sequential rebuild (no O(n^2))."""
    if not replacements:
        return bytes(raw_data)
    ordered = sorted(replacements, key=lambda item: item[0].value_offset)
    result = bytearray()
    cursor = 0
    for entry, new_value in ordered:
        if entry.value_offset < cursor:
            raise ValueError(f"Overlapping replacement at 0x{entry.value_offset:08X}")
        old_len = len(entry.value.encode("utf-8"))
        new_value_bytes = new_value.encode("utf-8")
        old_end = entry.value_offset + _U32SZ + old_len
        result.extend(raw_data[cursor:entry.value_offset])
        result.extend(_U32.pack(len(new_value_bytes)))
        result.extend(new_value_bytes)
        cursor = old_end
    result.extend(raw_data[cursor:])
    return bytes(result)


# ---------------------------------------------------------------------------
# .papgt reader/writer (meta/0.papgt - the root package-group index)
# ---------------------------------------------------------------------------
@dataclass
class PapgtGroupEntry:
    entry_index: int
    flags: int
    sequence: int
    pamt_crc: int
    entry_offset: int
    crc_offset: int


@dataclass
class PapgtData:
    path: str
    magic: int
    self_crc: int
    groups: list[PapgtGroupEntry]
    raw_data: bytes
    packages_path: str = ""


def parse_papgt(papgt_path: str) -> PapgtData:
    with open(papgt_path, "rb") as f:
        data = f.read()
    if len(data) < 12:
        raise ValueError(f"PAPGT too small: {papgt_path}")
    magic = struct.unpack_from("<I", data, 0)[0]
    self_crc = struct.unpack_from("<I", data, 4)[0]
    groups = []
    off = 12
    index = 0
    while off + 12 <= len(data):
        flags = struct.unpack_from("<I", data, off)[0]
        sequence = struct.unpack_from("<I", data, off + 4)[0]
        pamt_crc = struct.unpack_from("<I", data, off + 8)[0]
        groups.append(PapgtGroupEntry(index, flags, sequence, pamt_crc, off, off + 8))
        off += 12
        index += 1
    packages_path = ""
    papgt_dir = os.path.dirname(papgt_path)
    if os.path.basename(papgt_dir) == "meta":
        packages_path = os.path.dirname(papgt_dir)
    return PapgtData(papgt_path, magic, self_crc, groups, data, packages_path)


def _sorted_package_dirs(packages_path: str) -> list[str]:
    dirs = []
    for item in sorted(os.listdir(packages_path)):
        full = os.path.join(packages_path, item)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, "0.pamt")):
            dirs.append(item)
    return dirs


def get_pamt_crc_offset(papgt_data: PapgtData, folder_number: int) -> int:
    """PAPGT entries are POSITIONAL - match folder_number to its index
    in the sorted package-directory list (there is no folder id stored
    in the entry itself)."""
    packages_path = papgt_data.packages_path
    folder_name = f"{folder_number:04d}"
    sorted_dirs = _sorted_package_dirs(packages_path)
    if folder_name not in sorted_dirs:
        raise ValueError(f"Package folder {folder_name} not found under {packages_path}")
    index = sorted_dirs.index(folder_name)
    if index >= len(papgt_data.groups):
        raise ValueError(f"{folder_name} at position {index}, but only {len(papgt_data.groups)} papgt entries")
    return papgt_data.groups[index].crc_offset


def update_papgt_pamt_crc(papgt_raw: bytearray, crc_offset: int, new_pamt_crc: int) -> None:
    struct.pack_into("<I", papgt_raw, crc_offset, new_pamt_crc)


def update_papgt_self_crc(papgt_raw: bytearray) -> int:
    new_crc = pa_checksum(bytes(papgt_raw[12:]))
    struct.pack_into("<I", papgt_raw, 4, new_crc)
    return new_crc


def verify_papgt_checksum(papgt_path: str) -> tuple[bool, int, int]:
    with open(papgt_path, "rb") as f:
        data = f.read()
    stored = struct.unpack_from("<I", data, 4)[0]
    computed = pa_checksum(data[12:])
    return (stored == computed, stored, computed)


def verify_pamt_checksum(pamt_path: str) -> tuple[bool, int, int]:
    with open(pamt_path, "rb") as f:
        data = f.read()
    stored = struct.unpack_from("<I", data, 0)[0]
    computed = pa_checksum(data[12:])
    return (stored == computed, stored, computed)


# ---------------------------------------------------------------------------
# .pamt / .paz writers - update-in-place, matching pamt_parser field layout
# ---------------------------------------------------------------------------
def update_pamt_paz_entry(pamt_raw: bytearray, paz_table_entry: PazTableEntry,
                           new_checksum: int, new_size: int) -> None:
    struct.pack_into("<I", pamt_raw, paz_table_entry.entry_offset, new_checksum)
    struct.pack_into("<I", pamt_raw, paz_table_entry.entry_offset + 4, new_size)


def update_pamt_file_entry(pamt_raw: bytearray, file_entry: PamtFileEntry,
                            new_comp_size: int, new_orig_size: int,
                            new_offset: Optional[int] = None) -> None:
    if new_offset is not None:
        struct.pack_into("<I", pamt_raw, file_entry.record_offset + 4, new_offset)
    struct.pack_into("<I", pamt_raw, file_entry.record_offset + 8, new_comp_size)
    struct.pack_into("<I", pamt_raw, file_entry.record_offset + 12, new_orig_size)


def update_pamt_self_crc(pamt_raw: bytearray) -> int:
    new_crc = pa_checksum(bytes(pamt_raw[12:]))
    struct.pack_into("<I", pamt_raw, 0, new_crc)
    return new_crc


def _pad_to_16(data: bytes) -> bytes:
    rem = len(data) % 16
    if rem == 0:
        return data
    return data + b"\x00" * (16 - rem)


def build_space_map(entries: list[PamtFileEntry]) -> dict[tuple[str, int], int]:
    """Available-space map: how many bytes an entry may grow into
    in-place before requiring relocation (gap to the next entry by
    offset, or comp_size+16 if it's the last one in that paz)."""
    by_paz: dict[str, list[PamtFileEntry]] = {}
    for entry in entries:
        by_paz.setdefault(entry.paz_file, []).append(entry)
    space_map: dict[tuple[str, int], int] = {}
    for paz_path, paz_entries in by_paz.items():
        sorted_entries = sorted(paz_entries, key=lambda e: e.offset)
        for i, entry in enumerate(sorted_entries):
            if i + 1 < len(sorted_entries):
                gap = sorted_entries[i + 1].offset - entry.offset
            else:
                gap = entry.comp_size + 16
            space_map[(paz_path, entry.offset)] = max(gap, entry.comp_size)
    return space_map


def write_entry_payload(entry: PamtFileEntry, payload: bytes,
                         space_map: dict[tuple[str, int], int],
                         zero_old_region_on_relocate: bool = True) -> tuple[int, int]:
    """Write payload into a PAZ entry. Overwrites in place if it fits in
    the existing gap; otherwise appends (16-byte aligned) at EOF and
    zeros the vacated region. Returns (new_offset, logical_size)."""
    padded = _pad_to_16(payload)
    paz_path = entry.paz_file
    max_space = space_map.get((paz_path, entry.offset), entry.comp_size)

    if len(padded) <= max_space:
        with open(paz_path, "r+b") as f:
            f.seek(entry.offset)
            f.write(padded)
        new_offset = entry.offset
    else:
        paz_size = os.path.getsize(paz_path)
        aligned = (paz_size + 15) & ~15
        with open(paz_path, "r+b") as f:
            if zero_old_region_on_relocate:
                f.seek(entry.offset)
                f.write(b"\x00" * entry.comp_size)
            f.seek(paz_size)
            if aligned > paz_size:
                f.write(b"\x00" * (aligned - paz_size))
            f.write(padded)
        new_offset = aligned

    return new_offset, len(payload)


def compress(data: bytes, compression_type: int) -> bytes:
    if compression_type == COMP_NONE:
        return data
    if compression_type == COMP_LZ4:
        return lz4.block.compress(data, mode="default", store_size=False)
    if compression_type == COMP_ZLIB:
        return zlib.compress(data)
    raise ValueError(f"Unsupported compression type for write: {compression_type}")


# ---------------------------------------------------------------------------
# Top-level: patch translated paloc values into the live game, full chain.
# ---------------------------------------------------------------------------
@dataclass
class PatchResult:
    success: bool
    message: str
    paz_crc: int = 0
    pamt_crc: int = 0
    papgt_crc: int = 0
    errors: list = field(default_factory=list)


def patch_paloc_values(packages_path: str, group: str, filename: str,
                        replacements_by_key: dict[str, str]) -> PatchResult:
    """Splice new values into an already-shipped .paloc (by key), then
    re-compress + re-encrypt + write back through the FULL checksum
    chain (paz CRC -> pamt self-CRC -> papgt per-group CRC -> papgt
    self-CRC), verifying after. No backup here - caller's job (this
    project always keeps a pristine copy before any deploy)."""
    result = PatchResult(success=False, message="")
    try:
        group_dir = os.path.join(packages_path, group)
        pamt_path = os.path.join(group_dir, "0.pamt")
        papgt_path = os.path.join(packages_path, "meta", "0.papgt")

        pamt = parse_pamt(pamt_path, paz_dir=group_dir)
        entry = None
        needle = filename.lower()
        for cand in pamt.file_entries:
            if cand.path.lower().endswith(needle):
                entry = cand
                break
        if entry is None:
            raise FileNotFoundError(f"{filename} not found in group {group}")

        original_raw = read_file(entry)
        original_entries = parse_paloc(original_raw)
        by_key = {e.key: e for e in original_entries}

        replacements: list[tuple[PalocEntry, str]] = []
        for key, new_val in replacements_by_key.items():
            orig = by_key.get(key)
            if orig is None:
                result.errors.append(f"key not found, skipped: {key!r}")
                continue
            if new_val != orig.value:
                replacements.append((orig, new_val))

        paloc_raw = splice_values_in_raw(original_raw, replacements) if replacements else original_raw

        payload = paloc_raw
        if entry.compression_type == COMP_LZ4:
            payload = compress(payload, COMP_LZ4)
        elif entry.compression_type == COMP_ZLIB:
            payload = compress(payload, COMP_ZLIB)

        if entry.encrypted:
            payload = encrypt(payload, os.path.basename(entry.path))

        new_comp_size = len(payload)
        new_orig_size = len(paloc_raw)

        space_map = build_space_map(pamt.file_entries)
        new_offset, _ = write_entry_payload(entry, payload, space_map)

        new_paz_crc = pa_checksum(open(entry.paz_file, "rb").read())
        new_paz_size = os.path.getsize(entry.paz_file)
        result.paz_crc = new_paz_crc

        pamt2 = parse_pamt(pamt_path, paz_dir=group_dir)
        pamt_raw = bytearray(pamt2.raw_data)
        for t in pamt2.paz_table:
            if t.index == entry.paz_index:
                update_pamt_paz_entry(pamt_raw, t, new_paz_crc, new_paz_size)
                break
        for fe in pamt2.file_entries:
            if fe.record_offset == entry.record_offset:
                update_pamt_file_entry(pamt_raw, fe, new_comp_size, new_orig_size, new_offset=new_offset)
                break
        new_pamt_crc = update_pamt_self_crc(pamt_raw)
        result.pamt_crc = new_pamt_crc
        with open(pamt_path, "wb") as f:
            f.write(pamt_raw)

        papgt = parse_papgt(papgt_path)
        papgt_raw = bytearray(papgt.raw_data)
        crc_off = get_pamt_crc_offset(papgt, int(group))
        update_papgt_pamt_crc(papgt_raw, crc_off, new_pamt_crc)
        new_papgt_crc = update_papgt_self_crc(papgt_raw)
        result.papgt_crc = new_papgt_crc
        with open(papgt_path, "wb") as f:
            f.write(papgt_raw)

        ok_pamt, s1, c1 = verify_pamt_checksum(pamt_path)
        ok_papgt, s2, c2 = verify_papgt_checksum(papgt_path)
        if not ok_pamt:
            raise RuntimeError(f"PAMT checksum verify failed: stored=0x{s1:08X} computed=0x{c1:08X}")
        if not ok_papgt:
            raise RuntimeError(f"PAPGT checksum verify failed: stored=0x{s2:08X} computed=0x{c2:08X}")

        result.success = True
        result.message = f"Patched {len(replacements)} strings into {filename} (group {group})"
        return result
    except Exception as exc:
        result.errors.append(str(exc))
        result.message = str(exc)
        return result


def patch_raw_file(packages_path: str, group: str, filename: str,
                    new_bytes: bytes) -> PatchResult:
    """Replace one whole file's content (e.g. an unencrypted, uncompressed-
    at-rest-relative loose asset like a font TTF) inside a package group,
    through the same full checksum chain as patch_paloc_values. `filename`
    matches by endswith on the PAMT-recorded path (case-insensitive).
    No backup here - caller's job."""
    result = PatchResult(success=False, message="")
    try:
        group_dir = os.path.join(packages_path, group)
        pamt_path = os.path.join(group_dir, "0.pamt")
        papgt_path = os.path.join(packages_path, "meta", "0.papgt")

        pamt = parse_pamt(pamt_path, paz_dir=group_dir)
        entry = None
        needle = filename.lower()
        for cand in pamt.file_entries:
            if cand.path.lower().endswith(needle):
                entry = cand
                break
        if entry is None:
            raise FileNotFoundError(f"{filename} not found in group {group}")

        new_orig_size = len(new_bytes)
        payload = new_bytes
        if entry.compression_type == COMP_LZ4:
            payload = compress(payload, COMP_LZ4)
        elif entry.compression_type == COMP_ZLIB:
            payload = compress(payload, COMP_ZLIB)

        if entry.encrypted:
            payload = encrypt(payload, os.path.basename(entry.path))

        new_comp_size = len(payload)

        space_map = build_space_map(pamt.file_entries)
        new_offset, _ = write_entry_payload(entry, payload, space_map)

        new_paz_crc = pa_checksum(open(entry.paz_file, "rb").read())
        new_paz_size = os.path.getsize(entry.paz_file)
        result.paz_crc = new_paz_crc

        pamt2 = parse_pamt(pamt_path, paz_dir=group_dir)
        pamt_raw = bytearray(pamt2.raw_data)
        for t in pamt2.paz_table:
            if t.index == entry.paz_index:
                update_pamt_paz_entry(pamt_raw, t, new_paz_crc, new_paz_size)
                break
        for fe in pamt2.file_entries:
            if fe.record_offset == entry.record_offset:
                update_pamt_file_entry(pamt_raw, fe, new_comp_size, new_orig_size, new_offset=new_offset)
                break
        new_pamt_crc = update_pamt_self_crc(pamt_raw)
        result.pamt_crc = new_pamt_crc
        with open(pamt_path, "wb") as f:
            f.write(pamt_raw)

        papgt = parse_papgt(papgt_path)
        papgt_raw = bytearray(papgt.raw_data)
        crc_off = get_pamt_crc_offset(papgt, int(group))
        update_papgt_pamt_crc(papgt_raw, crc_off, new_pamt_crc)
        new_papgt_crc = update_papgt_self_crc(papgt_raw)
        result.papgt_crc = new_papgt_crc
        with open(papgt_path, "wb") as f:
            f.write(papgt_raw)

        ok_pamt, s1, c1 = verify_pamt_checksum(pamt_path)
        ok_papgt, s2, c2 = verify_papgt_checksum(papgt_path)
        if not ok_pamt:
            raise RuntimeError(f"PAMT checksum verify failed: stored=0x{s1:08X} computed=0x{c1:08X}")
        if not ok_papgt:
            raise RuntimeError(f"PAPGT checksum verify failed: stored=0x{s2:08X} computed=0x{c2:08X}")

        result.success = True
        result.message = f"Patched {filename} (group {group}), {len(new_bytes)} bytes"
        return result
    except Exception as exc:
        result.errors.append(str(exc))
        result.message = str(exc)
        return result


if __name__ == "__main__":
    import sys
    pamt_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not pamt_path:
        print("usage: cd_container.py <path-to-0.pamt> [filename-substring]")
        raise SystemExit(1)
    pamt = parse_pamt(pamt_path)
    print(f"pamt: {pamt_path}")
    print(f"  self_crc=0x{pamt.self_crc:08X} paz_count={pamt.paz_count} "
          f"files={len(pamt.file_entries)} prefix={pamt.folder_prefix!r}")
    needle = sys.argv[2] if len(sys.argv) > 2 else None
    for e in pamt.file_entries:
        if needle and needle.lower() not in e.path.lower():
            continue
        print(f"  {e.path}  paz={e.paz_index} off=0x{e.offset:X} "
              f"comp={e.comp_size} orig={e.orig_size} enc={e.encrypted} "
              f"comptype={e.compression_type}")
