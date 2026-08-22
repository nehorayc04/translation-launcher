#!/usr/bin/env python3
"""
AC2 (Assassin's Creed II) scimitar-v25 .forge reader  — READ-SIDE, pure Python.

Reverse-engineered against the real D:\\Games\\Assassin's Creed II forges
(2026-06-18). Parses the container index and extracts any sub-resource ("FILEDATA"
.data file) by name. This is the proven read path; the WRITE/repack of the inner
LocalizationPackage is done with AnvilToolkit (see ../PIPELINE.md) until a full
Python repacker is built.

Container layout (scimitar version 25):
  Header @0x00:
    char[8]  "scimitar"
    u8       0x00
    u32      version              (== 25 for AC2)
    i64      index_offset         (points at the "index header")
    ...
  Index header @ index_offset:
    u32  N                        (resource count)
    ...   (two i64 pointers at +0x20 and +0x30; +0x30 -> the record table)
  Record table @ ptr(+0x30), N entries of 16 bytes:
    i64  data_offset              (0x800-aligned -> padded on disk)
    u32  name_hash / misc
    u32  size                     (TRUE byte size of the resource)
  Descriptor table (188-byte entries, located generically by idB==0..5):
    char[128] name                (e.g. "LocalizationPackage_English")
    ... u32 idA@+172  u32 idB@+176  u32 0  u32 timestamp@+184
    idB is the 0-based resource index -> maps name -> record[idB].

Each extracted resource itself begins with:  "FILEDATA" + char[128] name + payload.

Usage:
    python ac2_forge.py <forge> list
    python ac2_forge.py <forge> extract <ResourceName> <out.bin>
    python ac2_forge.py <forge> grep <substr>
"""
import struct
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class Forge:
    STRIDE = 0xBC          # descriptor entry size (188)
    IDB = 0xBC - 12        # idB field offset within a descriptor (176)

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        d = self.data
        if d[:8] != b"scimitar":
            raise ValueError("not a scimitar forge: " + path)
        self.ver = struct.unpack_from("<I", d, 9)[0]
        self.idx = struct.unpack_from("<q", d, 13)[0]
        self.n = struct.unpack_from("<I", d, self.idx)[0]
        self.rec_ptr = struct.unpack_from("<q", d, self.idx + 0x30)[0]
        self._parse()

    def _parse(self):
        d = self.data
        # record table: 16 bytes each [i64 off][u32 a][u32 size]
        self.recs = []
        for i in range(self.n):
            o = self.rec_ptr + i * 16
            off = struct.unpack_from("<q", d, o)[0]
            a = struct.unpack_from("<I", d, o + 8)[0]
            size = struct.unpack_from("<I", d, o + 12)[0]
            self.recs.append((off, a, size))
        # Authoritative names come from each resource's own FILEDATA header
        # ("FILEDATA" + char[128] name) -> clean, no descriptor-prefix junk.
        self.names = [None] * self.n
        for i, (off, _a, _sz) in enumerate(self.recs):
            if d[off:off + 8] == b"FILEDATA":
                nm = d[off + 8:off + 8 + 128].split(b"\x00", 1)[0]
                self.names[i] = nm.decode("latin1", "replace")

    def _find_desc_table(self):
        """Find the descriptor-table origin: offset O where, for k=0..5,
        u32 @ O + k*STRIDE + IDB == k."""
        d = self.data
        first_off = min(o for (o, _, _) in self.recs)
        lo = self.rec_ptr + self.n * 16
        hi = min(first_off, len(d)) - self.STRIDE * 6
        for O in range(lo, hi):
            if all(struct.unpack_from("<I", d, O + k * self.STRIDE + self.IDB)[0] == k
                   for k in range(6)):
                return O
        raise RuntimeError("descriptor table not found in " + self.path)

    def size_of(self, i):
        return self.recs[i][2]

    def by_name(self, name):
        for i, nm in enumerate(self.names):
            if nm == name:
                return i
        return -1

    def extract(self, i):
        off = self.recs[i][0]
        return self.data[off:off + self.size_of(i)]

    def full_slot(self, i):
        """Full on-disk slot off[i]..off[next] — the record SIZE field excludes
        the FILEDATA header, so CFD payloads run past extract(i). Use this for
        anything that must read the WHOLE resource (font atlases, big loc)."""
        off = self.recs[i][0]
        nxt = min((o for (o, _, _) in self.recs if o > off), default=len(self.data))
        return self.data[off:nxt], off, nxt

    @staticmethod
    def write_resource(path, i, new_bytes):
        """Relocate resource i to a fresh 32 KB-aligned slot at EOF holding
        new_bytes, and patch its 16-byte record (offset + size). The descriptor
        table carries no offset/size, so only the record needs patching. This is
        the community 'extractor/replacer' append technique (in-game proven).
        Operates IN PLACE on `path` — copy the forge first."""
        fg = Forge(path)
        rec_o = fg.rec_ptr + i * 16
        with open(path, "r+b") as f:
            f.seek(0, 2)
            new_off = (f.tell() + 32767) & ~32767
            f.seek(new_off)
            f.write(new_bytes)
            end = f.tell()
            f.write(b"\x00" * (((end + 32767) & ~32767) - end))   # 32 KB align
            f.seek(rec_o)
            f.write(struct.pack("<q", new_off))                   # offset
            f.seek(rec_o + 12)
            f.write(struct.pack("<I", len(new_bytes)))            # size
        return new_off

    def payload(self, i):
        """Resource bytes with the FILEDATA(8)+name(128) header stripped."""
        blob = self.extract(i)
        assert blob[:8] == b"FILEDATA", "unexpected resource header"
        return blob[8 + 128:]


def _main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    forge, cmd = argv[1], argv[2]
    fg = Forge(forge)
    if cmd == "list":
        print(f"# {os.path.basename(forge)}  ver={fg.ver}  N={fg.n}")
        for i in range(fg.n):
            print(f"  [{i:4}] {fg.size_of(i):>11,}  {fg.names[i]}")
    elif cmd == "grep":
        sub = argv[3]
        for i in range(fg.n):
            if fg.names[i] and sub.lower() in fg.names[i].lower():
                print(f"  [{i:4}] {fg.size_of(i):>11,}  {fg.names[i]}")
    elif cmd == "extract":
        name, out = argv[3], argv[4]
        i = fg.by_name(name)
        if i < 0:
            print("not found:", name)
            return 2
        with open(out, "wb") as f:
            f.write(fg.extract(i))
        print(f"wrote {out}  ({fg.size_of(i):,} B)  index={i}")
    else:
        print("unknown command:", cmd)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
