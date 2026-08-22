#!/usr/bin/env python3
"""
mirage_forge.py — Assassin's Creed Mirage (AnvilNext) scimitar-**v29** .forge reader.
Pure Python, READ-ONLY, no deps.

Layout derived from a decompile of the FREE public AnvilToolkit v1.3.4
(`ForgeFile.Deserialize29` / `FileSet(BinaryReader,…)` / `ForgeEntry(BinaryReader,…)`),
then validated against the real F:\\Game Lab\\Assassin's Creed Mirage forges.

  Header:
    0x00  char[8] "scimitar" + u8 0x00
    0x09  u32   version                (== 29 for Mirage / Valhalla)
    0x0d  i64   header_size            (== 1050 = 0x41a)
    ...   header blob
    1050  i64   total_entry_count
          i64   0
          i32   -1
          i64   -1
          i32   entry_count + 6
          i32   fileset_count
          i64   first_fileset_offset   (== 1094)

  FileSet @ offset:
    +0x00 u32  count            (entries in THIS set)
    +0x04 u32  ?
    +0x08 i64  ?
    +0x10 i64  next_fileset_offset      (-1 = last)
    +0x18 i32  ?
    +0x1c i32  ?
    +0x20 i64  info_table_offset        (UNUSED on v29 — see below)
    +0x28 i64  ?
    +0x30 entries[count], 20 bytes each:
            i64 offset ; u64 id ; i32 length_on_disk

  🔴 v29 has NO NAME TABLE. AnvilToolkit does `Entry.Name = ID.GetOriginalFileName()`
  — a hash→name lookup from an external database. Resources are addressed by the
  numeric u64 ID only (same as AC Shadows v42, unlike AC2 v25 / Unity v27 which
  carry plaintext names in a descriptor table). Find a resource by CONTENT
  (its ScimitarClass hash), not by name.

Usage:
    python mirage_forge.py <forge> info
    python mirage_forge.py <forge> list [--limit N]
    python mirage_forge.py <forge> extract <id|#index> <out.bin>
"""
import argparse
import os
import struct
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAGIC = b"scimitar"
REC_SIZE = 20
FILESET_HDR = 0x30


class Entry:
    __slots__ = ("index", "offset", "id", "size", "rec_pos")

    def __init__(self, index, offset, eid, size, rec_pos=0):
        self.index = index
        self.offset = offset
        self.id = eid
        self.size = size
        self.rec_pos = rec_pos        # absolute file offset of this 20-byte record

    def __repr__(self):
        return f"<Entry #{self.index} id={self.id} off=0x{self.offset:x} size={self.size}>"


class Forge:
    def __init__(self, path):
        self.path = path
        self.fsz = os.path.getsize(path)
        self.f = open(path, "rb")
        head = self.f.read(64)
        if head[:8] != MAGIC:
            raise ValueError(f"not a scimitar forge: {path}")
        self.ver = struct.unpack_from("<I", head, 9)[0]
        self.header_size = struct.unpack_from("<q", head, 13)[0]
        if self.ver != 29:
            print(f"[warn] version {self.ver} != 29 — layout may differ", file=sys.stderr)

        self.f.seek(self.header_size)
        blk = self.f.read(48)
        (self.total_count, _zero, _m1a) = struct.unpack_from("<qqi", blk, 0)
        (_m1b, self.count_plus6, self.fileset_count) = struct.unpack_from("<qii", blk, 20)
        self.first_fileset = struct.unpack_from("<q", blk, 36)[0]

        self.entries = []
        self._read_filesets()

    def _read_filesets(self):
        off = self.first_fileset
        idx = 0
        seen = set()
        while off != -1 and off > 0 and off < self.fsz:
            if off in seen:
                break
            seen.add(off)
            self.f.seek(off)
            hdr = self.f.read(FILESET_HDR)
            if len(hdr) < FILESET_HDR:
                break
            count = struct.unpack_from("<I", hdr, 0)[0]
            nxt = struct.unpack_from("<q", hdr, 0x10)[0]
            rec_base = off + FILESET_HDR
            raw = self.f.read(count * REC_SIZE)
            for i in range(count):
                o, eid, size = struct.unpack_from("<qQi", raw, i * REC_SIZE)
                self.entries.append(Entry(idx, o, eid, size, rec_base + i * REC_SIZE))
                idx += 1
            off = nxt

    # ---------------------------------------------------------------- api
    def by_id(self, eid):
        return [e for e in self.entries if e.id == eid]

    def read(self, e):
        self.f.seek(e.offset)
        return self.f.read(e.size)

    def validate(self):
        """Contiguity / sanity checks — the cheap proof the layout is right."""
        bad = 0
        prev_end = None
        for e in self.entries:
            if e.offset <= 0 or e.offset + e.size > self.fsz or e.size <= 0:
                bad += 1
            if prev_end is not None and e.offset < prev_end:
                bad += 1
            prev_end = e.offset + e.size
        return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["info", "list", "extract"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    fg = Forge(a.forge)

    if a.cmd == "info":
        print(f"file          : {a.forge}")
        print(f"size          : {fg.fsz:,}")
        print(f"version       : {fg.ver}")
        print(f"header_size   : {fg.header_size} (0x{fg.header_size:x})")
        print(f"total_count   : {fg.total_count:,}")
        print(f"count+6       : {fg.count_plus6:,}")
        print(f"fileset_count : {fg.fileset_count}")
        print(f"first_fileset : {fg.first_fileset}")
        print(f"entries read  : {len(fg.entries):,}")
        print(f"validate bad  : {fg.validate()}")
        return

    if a.cmd == "list":
        for e in fg.entries[: a.limit]:
            print(f"  [{e.index:6}] id={e.id:<22} off=0x{e.offset:010x} size={e.size:>12,}")
        return

    if a.cmd == "extract":
        key, out = a.args[0], a.args[1]
        if key.startswith("#"):
            e = fg.entries[int(key[1:])]
        else:
            m = fg.by_id(int(key))
            if not m:
                sys.exit(f"id {key} not found")
            e = m[0]
        data = fg.read(e)
        with open(out, "wb") as fh:
            fh.write(data)
        print(f"wrote {len(data):,} bytes from {e} -> {out}")


if __name__ == "__main__":
    main()
