"""Forza Horizon 6 (ForzaTech) `.str` string-table codec — pure Python, no deps.

Layout (little-endian), reversed from the shipped tables:

    +0x00  u16   version            (0x0800 on every shipped table)
    +0x02  char[128] name           NUL-padded table name, e.g. "ButtonPanel"
    +0x82  u16   sectionCount       (always 2)
    +0x84  u32   sectionOffset[N]   absolute file offsets

    section:
        +0  u32  totalSize          == count*8 + blobLen
        +4  u32  blobLen
        +8  u32  count
        +12 {u32 hash, u32 offset} * count      offset = byte index into blob
        ..  blob                                NUL-terminated UTF-8 strings

    section[0] = the VALUES (what the player reads)
    section[1] = the ID NAMES (`IDS_Foo`) — SAME hash array, so the two
                 sections are keyed by one string id.

Two properties that decide the write path:
  * the offset table is explicit per entry, so the blob layout is free;
  * the hash is a content hash of the id name, and a translation only ever
    replaces VALUES for EXISTING ids -> the hash array is copied verbatim and
    the hash function never has to be reimplemented.

`edit()` is therefore SURGICAL: the original value blob is kept byte-for-byte
and changed strings are APPENDED at its end, so `edit(buf, {})` is byte-identical
to the input on every shipped table.
"""
from __future__ import annotations

import struct
from typing import Dict, List

NAME_LEN = 128
HDR = 2 + NAME_LEN  # 0x82


class Section:
    __slots__ = ("hashes", "offsets", "blob")

    def __init__(self, hashes: List[int], offsets: List[int], blob: bytes):
        self.hashes = hashes
        self.offsets = offsets
        self.blob = blob

    def strings(self) -> List[str]:
        out = []
        for o in self.offsets:
            end = self.blob.index(b"\x00", o)
            out.append(self.blob[o:end].decode("utf-8"))
        return out

    def to_bytes(self) -> bytes:
        ent = b"".join(struct.pack("<II", h, o)
                       for h, o in zip(self.hashes, self.offsets))
        return (struct.pack("<III", len(ent) + len(self.blob),
                            len(self.blob), len(self.hashes))
                + ent + bytes(self.blob))


class StrTable:
    __slots__ = ("version", "name", "vals", "ids")

    def __init__(self, version: int, name: str, vals: Section, ids: Section):
        self.version = version
        self.name = name
        self.vals = vals
        self.ids = ids

    def __len__(self) -> int:
        return len(self.vals.hashes)

    @property
    def hashes(self) -> List[int]:
        return self.vals.hashes

    def values(self) -> List[str]:
        return self.vals.strings()

    def id_names(self) -> List[str]:
        return self.ids.strings()

    def as_dict(self) -> Dict[str, str]:
        """{IDS_name: value} — the human-facing view."""
        return dict(zip(self.id_names(), self.values()))

    def to_bytes(self) -> bytes:
        s0 = self.vals.to_bytes()
        s1 = self.ids.to_bytes()
        off0 = HDR + 2 + 2 * 4
        head = struct.pack("<H", self.version)
        head += self.name.encode("utf-8").ljust(NAME_LEN, b"\x00")
        head += struct.pack("<HII", 2, off0, off0 + len(s0))
        return head + s0 + s1


def _read_section(buf: bytes, off: int) -> Section:
    total, blob_len, count = struct.unpack_from("<III", buf, off)
    if total != count * 8 + blob_len:
        raise ValueError(f"section size mismatch at {off}: "
                         f"{total} != {count}*8 + {blob_len}")
    ent = off + 12
    blob_at = ent + count * 8
    hashes, offsets = [], []
    for i in range(count):
        h, o = struct.unpack_from("<II", buf, ent + i * 8)
        if o >= blob_len:
            raise ValueError(f"offset {o} out of blob ({blob_len})")
        hashes.append(h)
        offsets.append(o)
    return Section(hashes, offsets, buf[blob_at:blob_at + blob_len])


def parse(buf: bytes) -> StrTable:
    version = struct.unpack_from("<H", buf, 0)[0]
    name = buf[2:2 + NAME_LEN].split(b"\x00", 1)[0].decode("utf-8")
    n = struct.unpack_from("<H", buf, HDR)[0]
    if n != 2:
        raise ValueError(f"unexpected section count {n} in {name!r}")
    offs = struct.unpack_from("<%dI" % n, buf, HDR + 2)
    vals = _read_section(buf, offs[0])
    ids = _read_section(buf, offs[1])
    if vals.hashes != ids.hashes:
        raise ValueError(f"{name}: value/id hash arrays differ")
    return StrTable(version, name, vals, ids)


def edit(buf: bytes, new_values: Dict[str, str]) -> bytes:
    """Rebuild `buf` with `{IDS_name: new_value}` applied, SURGICALLY:
    the original blob is preserved verbatim and replacements are appended,
    so an empty edit is byte-identical and untouched strings never move."""
    t = parse(buf)
    if not new_values:
        return t.to_bytes()
    ids = t.id_names()
    blob = bytearray(t.vals.blob)
    appended: Dict[str, int] = {}
    offs = list(t.vals.offsets)
    for i, idn in enumerate(ids):
        nv = new_values.get(idn)
        if nv is None:
            continue
        o = appended.get(nv)
        if o is None:
            o = len(blob)
            appended[nv] = o
            blob += nv.encode("utf-8") + b"\x00"
        offs[i] = o
    t.vals = Section(t.vals.hashes, offs, bytes(blob))
    return t.to_bytes()


def is_table(filename: str) -> bool:
    return filename.lower().endswith(".str")


if __name__ == "__main__":  # identity round-trip over a whole language zip
    import sys, zipfile
    zp = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Games\Forza Horizon 6\media\Stripped\StringTables\EN.zip"
    z = zipfile.ZipFile(zp)
    ok = bad = 0
    total = 0
    for info in z.infolist():
        if not is_table(info.filename):
            continue
        raw = z.read(info.filename)
        try:
            t = parse(raw)
            total += len(t)
            if edit(raw, {}) == raw:
                ok += 1
            else:
                bad += 1
                print(f"  DIFF {info.filename}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"  FAIL {info.filename}: {e}")
    print(f"{zp}\n  byte-identical {ok}/{ok + bad}   entries {total}")
