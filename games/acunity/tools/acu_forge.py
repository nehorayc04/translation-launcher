#!/usr/bin/env python3
"""
acu_forge.py — AC Unity (AnvilNext 2.0) scimitar-v27 .forge reader. READ-SIDE, pure Python.

Reverse-engineered against the real E:\\Games\\Assassin's Creed Unity forges
(2026-07-01). Parses the container index + the 192-byte descriptor table and
extracts any sub-resource by NAME. This is the proven read path; the write/repack
of a resource (and the inner LocalizationPackage char-index decode) are later gates.

Container layout (scimitar version 27 — verified on DataPC.forge / DataPC_extra.forge):

  Header @0x00:
    char[8]  "scimitar"
    u8       0x00
    u32      version                 (== 27 for AC Unity)
    i64      index_offset            (@ file offset 13)
  Index @ index_offset:
    u32      file_count              (@ +0x00)  e.g. 1620
    ... a small linked-chunk preamble ...
    (the record array begins at index_offset + 0x70)
  Record array @ index_offset+0x70, `file_count` entries of 20 bytes each:
    u64  data_offset                 (on-disk offset of the resource blob; 0 = terminator)
    u32  file_id                     (resource id / lower hash)
    u32  flags
    u32  uncompressed_size
  Descriptor table @ record_array_end, FIXED 192-byte (0xC0) entries:
    +0x20  u32 record_index          (which record this descriptor names)
    +0x2b  char name[]               ('T'-prefixed, null-terminated, padded)
    (descriptor[0] == "TGlobalMetaFile" is a special header; index field = 0xFFFFFFFF)
  On-disk resource size = next_record_offset - data_offset  (records are contiguous,
  the u32 uncompressed_size is the DECOMPRESSED size, differs when the blob's inner
  DataFile chunks are compressed).

Each resource blob is a chain of Anvil "DataFile" chunks starting with:
    u32 0x57FBAA33 ; u32 0x1004FA99 ; ... ; (compressed or stored payload)
Decoding those chunks (the codec) is a separate gate — see PIPELINE.md.

Usage:
    python acu_forge.py <forge> list [--limit N] [--grep SUBSTR]
    python acu_forge.py <forge> names [--grep SUBSTR]
    python acu_forge.py <forge> extract <ResourceName> <out.bin>
    python acu_forge.py <forge> extract-index <i> <out.bin>
"""
import struct
import os
import sys
import bisect
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MAGIC = b"scimitar"
DESC_STRIDE = 0xC0          # 192-byte fixed descriptor entries
DESC_NAME_OFF = 0x2b        # name char[] offset within a descriptor
DESC_INDEX_OFF = 0x20       # u32 record-index within a descriptor
REC_PREAMBLE = 0x70         # record array starts at index_offset + 0x70


class Forge:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.fsz = os.path.getsize(path)
        head = self.f.read(64)
        if head[:8] != MAGIC:
            raise ValueError("not a scimitar forge: " + path)
        self.ver = struct.unpack_from("<I", head, 9)[0]
        self.index_off = struct.unpack_from("<q", head, 13)[0]
        self.f.seek(self.index_off)
        self.count = struct.unpack_from("<I", self.f.read(4), 0)[0]
        self.rec_start = self.index_off + REC_PREAMBLE
        self._read_records()
        self._read_names()

    def _read_records(self):
        self.f.seek(self.rec_start)
        raw = self.f.read(self.count * 20)
        self.recs = []                       # (offset, file_id, flags, usize)
        for i in range(self.count):
            self.recs.append(struct.unpack_from("<QIII", raw, i * 20))
        self._sorted_offs = sorted(o for (o, _, _, _) in self.recs if o > 0)

    def _read_names(self):
        """Parse the fixed 192-byte descriptor table -> {name: record_index}."""
        name_tab = self.rec_start + self.count * 20
        first_data = self._sorted_offs[0]
        region_len = first_data - name_tab
        self.f.seek(name_tab)
        region = self.f.read(region_len)
        self.name_to_index = {}
        self.index_to_name = {}
        n_desc = region_len // DESC_STRIDE
        for k in range(n_desc):
            base = k * DESC_STRIDE
            ridx = struct.unpack_from("<I", region, base + DESC_INDEX_OFF)[0]
            raw = region[base + DESC_NAME_OFF: base + DESC_STRIDE]
            nm = raw.split(b"\x00", 1)[0].decode("latin1", "replace")
            if not nm:
                continue
            if ridx != 0xFFFFFFFF and ridx < self.count:
                self.name_to_index[nm] = ridx
                self.index_to_name[ridx] = nm

    def disk_size(self, i):
        off = self.recs[i][0]
        if off == 0:
            return 0
        j = bisect.bisect_right(self._sorted_offs, off)
        nxt = self._sorted_offs[j] if j < len(self._sorted_offs) else self.fsz
        return nxt - off

    def extract_index(self, i):
        off = self.recs[i][0]
        self.f.seek(off)
        return self.f.read(self.disk_size(i))

    def extract(self, name):
        i = self.name_to_index.get(name)
        if i is None:
            return None, None
        return i, self.extract_index(i)


def _main(argv):
    ap = argparse.ArgumentParser(description="AC Unity scimitar-v27 forge reader (read-only)")
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["list", "names", "extract", "extract-index"])
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--grep", default=None)
    a = ap.parse_args(argv[1:])
    fg = Forge(a.forge)
    if a.cmd == "list":
        print(f"# {os.path.basename(a.forge)}  ver={fg.ver}  count={fg.count}  "
              f"index@0x{fg.index_off:x}  named={len(fg.name_to_index)}")
        shown = 0
        for i in range(fg.count):
            nm = fg.index_to_name.get(i, "")
            if a.grep and a.grep.lower() not in nm.lower():
                continue
            off, fid, fl, usz = fg.recs[i]
            print(f"  [{i:5}] off=0x{off:010x} fid={fid:>10} fl={fl:>3} usz={usz:>9,} disk={fg.disk_size(i):>9,}  {nm}")
            shown += 1
            if shown >= a.limit:
                break
    elif a.cmd == "names":
        for nm, i in sorted(fg.name_to_index.items()):
            if a.grep and a.grep.lower() not in nm.lower():
                continue
            print(f"  [{i:5}]  {nm}")
    elif a.cmd == "extract":
        name, out = a.rest[0], a.rest[1]
        i, blob = fg.extract(name)
        if blob is None:
            print("not found:", name)
            return 2
        open(out, "wb").write(blob)
        print(f"wrote {out}  record={i}  {len(blob):,} B (usz={fg.recs[i][3]:,})")
    elif a.cmd == "extract-index":
        i, out = int(a.rest[0]), a.rest[1]
        open(out, "wb").write(fg.extract_index(i))
        print(f"wrote {out}  record={i}  {fg.disk_size(i):,} B  name={fg.index_to_name.get(i,'')}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
