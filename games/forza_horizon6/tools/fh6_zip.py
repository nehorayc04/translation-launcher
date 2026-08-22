"""ForzaTech ZIP reader/writer — preserves the game's own 4 KB alignment.

A ForzaTech `media\\*.zip` is a normal ZIP with one private convention:

  * every entry's COMPRESSED DATA starts on a 4096-byte boundary;
  * the LOCAL header's extra field is a single padding record
        {u16 id 0x1123}{u16 len}{len zero bytes}
    sized so that `header_offset + 30 + len(name) + len(extra)` lands exactly
    on that boundary;
  * the CENTRAL directory carries {u16 0x1123}{u16 4}{u32 alignedDataOffset}.

Verified 288/288 on the xxh128-pristine EN.zip and GB.zip.

Consequences for reading:
  * the aligned offset in the CD extra is the authoritative data start;
  * a stale `compress_size` must NOT bound the inflate — feed the decompressor
    generously and let the deflate stream terminate itself, otherwise a
    partially-updated archive reads as "unknown codec".

Consequences for writing:
  * untouched entries are STREAM-COPIED (their original compressed bytes are
    reused), so a no-op rebuild is byte-identical and only what we changed moves.
"""
from __future__ import annotations

import struct
import zipfile
import zlib
from typing import Dict, List, Optional, Tuple

ALIGN = 4096
EXTRA_ID = 0x1123


class Entry:
    __slots__ = ("name", "comp", "method", "crc", "size", "date_time", "flag",
                 "create_version", "extract_version", "external_attr", "internal_attr")

    def __init__(self, name, comp, method, crc, size, date_time, flag,
                 create_version, extract_version, external_attr, internal_attr):
        self.name = name
        self.comp = comp                # raw compressed bytes as they go on disk
        self.method = method
        self.crc = crc
        self.size = size                # uncompressed size
        self.date_time = date_time
        self.flag = flag
        self.create_version = create_version
        self.extract_version = extract_version
        self.external_attr = external_attr
        self.internal_attr = internal_attr


def _aligned_offset(info: zipfile.ZipInfo) -> Optional[int]:
    p, ex = 0, info.extra
    while p + 4 <= len(ex):
        hid, hsz = struct.unpack_from("<HH", ex, p)
        if hid == EXTRA_ID and hsz == 4:
            return struct.unpack_from("<I", ex, p + 4)[0]
        p += 4 + hsz
    return None


def read(path: str) -> Tuple[List[Entry], Dict[str, bytes]]:
    """-> (entries in on-disk order, {name: decompressed bytes or b'' if unreadable})"""
    z = zipfile.ZipFile(path)
    with open(path, "rb") as f:
        data = f.read()
    infos = sorted(z.infolist(), key=lambda i: (_aligned_offset(i) or i.header_offset))
    entries: List[Entry] = []
    payload: Dict[str, bytes] = {}
    for idx, i in enumerate(infos):
        off = _aligned_offset(i)
        if off is None:
            sig, ver, flg, meth, t, d, crc, cs, us, nl, el = struct.unpack_from(
                "<IHHHHHIIIHH", data, i.header_offset)
            off = i.header_offset + 30 + nl + el
        # a stale compress_size must not bound us: run to the next entry's start
        nxt = (_aligned_offset(infos[idx + 1]) if idx + 1 < len(infos) else None)
        end = nxt if nxt else len(data)
        raw = data[off:end]
        if i.compress_type == zipfile.ZIP_DEFLATED:
            d = zlib.decompressobj(-15)
            try:
                out = d.decompress(raw)
                used = len(raw) - len(d.unused_data)
            except zlib.error:
                out, used = b"", i.compress_size
            if len(out) != i.file_size:
                out = b""                        # genuinely unreadable (corrupt file)
                used = i.compress_size
        else:
            out = raw[:i.file_size]
            used = i.file_size
        entries.append(Entry(i.filename, data[off:off + used], i.compress_type,
                             i.CRC, i.file_size, i.date_time, i.flag_bits,
                             i.create_version, i.extract_version,
                             i.external_attr, i.internal_attr))
        payload[i.filename] = out
    return entries, payload


def _pad_extra(need: int) -> bytes:
    """A 0x1123 padding record occupying exactly `need` bytes (need >= 4)."""
    return struct.pack("<HH", EXTRA_ID, need - 4) + b"\x00" * (need - 4)


def write(path: str, entries: List[Entry]) -> None:
    out = bytearray()
    cd = bytearray()
    for e in entries:
        name = e.name.encode("utf-8")
        base = len(out) + 30 + len(name)
        need = (-base) % ALIGN
        if need < 4:                    # a record needs >= 4 bytes of room
            need += ALIGN
        extra = _pad_extra(need)
        dosdate = ((e.date_time[0] - 1980) << 9) | (e.date_time[1] << 5) | e.date_time[2]
        dostime = (e.date_time[3] << 11) | (e.date_time[4] << 5) | (e.date_time[5] // 2)
        hdr_off = len(out)
        out += struct.pack("<IHHHHHIIIHH", 0x04034B50, e.extract_version, e.flag,
                           e.method, dostime, dosdate, e.crc, len(e.comp), e.size,
                           len(name), len(extra)) + name + extra
        assert len(out) % ALIGN == 0, "alignment invariant broken"
        data_off = len(out)
        out += e.comp
        cd += (struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, e.create_version,
                           e.extract_version, e.flag, e.method, dostime, dosdate,
                           e.crc, len(e.comp), e.size, len(name), 8, 0, 0,
                           e.internal_attr, e.external_attr, hdr_off)
               + name + struct.pack("<HHI", EXTRA_ID, 4, data_off))
    cd_off = len(out)
    out += cd
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(entries), len(entries),
                       len(cd), cd_off, 0)
    with open(path, "wb") as f:
        f.write(bytes(out))


def rebuild(src: str, dst: str, replace: Dict[str, bytes], level: int = 9) -> None:
    """Copy `src` to `dst`, re-deflating only the entries named in `replace`."""
    entries, _ = read(src)
    for e in entries:
        nv = replace.get(e.name)
        if nv is None:
            continue
        e.comp = zlib.compress(nv, level)[2:-4]     # raw deflate
        e.method = zipfile.ZIP_DEFLATED
        e.crc = zlib.crc32(nv) & 0xFFFFFFFF
        e.size = len(nv)
    write(dst, entries)


if __name__ == "__main__":
    import sys, os, hashlib
    src = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Games\Forza Horizon 6\media\Stripped\StringTables\EN.zip"
    tmp = os.path.join(os.environ.get("TEMP", "."), "fh6_zip_selftest.zip")
    ents, pay = read(src)
    unread = [n for n, v in pay.items() if not v and n.endswith(".str")]
    rebuild(src, tmp, {})
    a = hashlib.sha256(open(src, "rb").read()).hexdigest()
    b = hashlib.sha256(open(tmp, "rb").read()).hexdigest()
    e2, p2 = read(tmp)
    same_payload = all(pay[k] == p2.get(k) for k in pay)
    print(f"{os.path.basename(src)}: {len(ents)} entries, unreadable {len(unread)}")
    print(f"  no-op rebuild byte-identical : {a == b}")
    print(f"  payloads identical           : {same_payload}")
    os.remove(tmp)
