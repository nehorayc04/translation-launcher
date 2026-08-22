#!/usr/bin/env python3
"""
rda_reader.py - READ-ONLY reader for Anno 1800 "Resource File V2.2" (RDA) archives.

Pure stdlib + zlib. Never loads a whole .rda into RAM: it SEEKs the tail/header,
walks the singly-linked block chain (each block header points to the NEXT block),
reads only each block's directory + the one file you extract.

Format verified empirically against en_us0.rda and cross-checked against the
canonical reference RDAExplorer (lysannschlegel/RDAExplorer, RDAReader.cs /
BlockInfo.cs / DirEntry.cs / FileHeader.cs).

== RDA "Resource File V2.2" LAYOUT ==

Header (792 bytes / 0x318):
    magic        : 18 bytes  ASCII "Resource File V2.2"
    unknown      : 766 bytes (zero padding)
    firstBlockOffset : u64 LE  <- at file offset 784 (0x310); points to the FIRST
                                   block's 32-byte BlockInfo struct.
File data section begins right after the header (offset 0x318).

Block chain - each block laid out as: [ file-data... ][ directory ][ BlockInfo(32) ]
The firstBlockOffset points to a BlockInfo struct; you read it, process the block,
then follow blockInfo.nextBlock to the next BlockInfo, until nextBlock == filesize
(terminator: a block whose nextBlock points at EOF).

BlockInfo (V2.2, 32 bytes, at `blockOffset`):
    flags            : u32 LE   bit0=Compressed(zlib) bit1=Encrypted
                                 bit2=MemoryResident   bit3=Deleted/skip
    fileCount        : u32 LE
    directorySize    : u64 LE   (compressed size of the directory blob)
    decompressedSize : u64 LE   (== fileCount * 560; uncompressed directory size)
    nextBlock        : u64 LE   (offset of the next BlockInfo, or filesize at end)

The directory blob lives at  [blockOffset - directorySize]  (memory-resident
blocks shift back another 16 bytes). If flags bit0 set, zlib-uncompress it to
decompressedSize. It is fileCount * DirEntry records.

DirEntry (V2.2, 560 bytes):
    name        : 520 bytes  UTF-16LE, 260 chars, NUL-padded (in-archive path)
    offset      : u64 LE   absolute file offset of this file's bytes
    compressed  : u64 LE   on-disk byte length
    filesize    : u64 LE   uncompressed byte length
    timestamp   : u64 LE   unix time
    unknown     : u64 LE

Per-file: read `compressed` bytes at `offset`; if the OWNING BLOCK had the
Compressed flag, zlib-uncompress to `filesize`. (V2.0 block headers are 20 bytes
with u32 fields; this reader targets V2.2, which Anno 1800 uses.)
"""
import os
import struct
import sys
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAGIC_2_2 = b"Resource File V2.2"
HEADER_SIZE = 18 + 766 + 8          # 792 = 0x318
FIRST_BLOCK_OFF_POS = 18 + 766      # 784 = 0x310
BLOCKINFO_SIZE = 32
DIRENTRY_SIZE = 560
NAME_BYTES = 520

FLAG_COMPRESSED = 1
FLAG_ENCRYPTED = 2
FLAG_MEMRES = 4
FLAG_DELETED = 8


class RDAEntry:
    __slots__ = ("name", "offset", "compressed", "filesize", "timestamp",
                 "block_compressed", "block_encrypted")

    def __init__(self, name, offset, compressed, filesize, timestamp,
                 block_compressed, block_encrypted):
        self.name = name
        self.offset = offset
        self.compressed = compressed
        self.filesize = filesize
        self.timestamp = timestamp
        self.block_compressed = block_compressed
        self.block_encrypted = block_encrypted

    @property
    def is_compressed(self):
        return self.block_compressed

    def __repr__(self):
        c = "z" if self.block_compressed else "-"
        return f"<{self.name} off={self.offset} csz={self.compressed} usz={self.filesize} {c}>"


class RDAArchive:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.f.seek(0, 2)
        self.filesize = self.f.tell()
        self.f.seek(0)
        magic = self.f.read(18)
        if magic != MAGIC_2_2:
            raise ValueError(f"Not a V2.2 RDA (magic={magic!r}) in {path}")
        self.f.seek(FIRST_BLOCK_OFF_POS)
        (self.first_block_offset,) = struct.unpack("<Q", self.f.read(8))

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def iter_entries(self):
        """Walk the block chain, yielding RDAEntry. Reads only directories."""
        block_off = self.first_block_offset
        seen = set()
        while block_off and block_off < self.filesize and block_off not in seen:
            seen.add(block_off)
            self.f.seek(block_off)
            raw = self.f.read(BLOCKINFO_SIZE)
            if len(raw) < BLOCKINFO_SIZE:
                break
            flags, file_count, dir_size, decomp_size, next_block = struct.unpack("<IIQQQ", raw)
            if flags & FLAG_DELETED:
                block_off = next_block
                continue
            compressed = bool(flags & FLAG_COMPRESSED)
            encrypted = bool(flags & FLAG_ENCRYPTED)
            memres = bool(flags & FLAG_MEMRES)

            dir_pos = block_off - dir_size
            if memres:
                dir_pos -= 16  # two version-aware u64s
            if dir_pos < 0:
                break
            self.f.seek(dir_pos)
            blob = self.f.read(dir_size)
            if encrypted:
                # Anno 1800 base/lang archives are not encrypted; skip if seen.
                block_off = next_block
                continue
            if compressed:
                blob = zlib.decompress(blob)
            # blob is fileCount * 560
            for i in range(file_count):
                rec = blob[i * DIRENTRY_SIZE:(i + 1) * DIRENTRY_SIZE]
                if len(rec) < DIRENTRY_SIZE:
                    break
                name = rec[:NAME_BYTES].decode("utf-16le", "replace").split("\x00", 1)[0]
                offset, comp, fsize, ts, _unk = struct.unpack("<QQQQQ", rec[NAME_BYTES:NAME_BYTES + 40])
                yield RDAEntry(name, offset, comp, fsize, ts, compressed, encrypted)
            block_off = next_block

    def extract_entry(self, entry):
        """Return the decompressed bytes of one entry."""
        self.f.seek(entry.offset)
        data = self.f.read(entry.compressed)
        if entry.block_compressed:
            data = zlib.decompress(data)
        return data

    def read_blocks(self):
        """Return the archive as a list of blocks; each block is a list of (name, data_bytes),
        preserving the original per-block grouping (needed to rewrite in Anno's exact layout)."""
        blocks, cur, cur_block = [], None, None
        for e in self.iter_entries():
            b = (e.offset, e.compressed)  # cheap key; group by the block via a marker approach below
            del b
        # iter_entries doesn't expose block ids, so re-walk here directly:
        blocks = []
        block_off = self.first_block_offset
        seen = set()
        while block_off and block_off < self.filesize and block_off not in seen:
            seen.add(block_off)
            self.f.seek(block_off)
            raw = self.f.read(BLOCKINFO_SIZE)
            if len(raw) < BLOCKINFO_SIZE:
                break
            flags, file_count, dir_size, decomp_size, next_block = struct.unpack("<IIQQQ", raw)
            if flags & FLAG_DELETED:
                block_off = next_block
                continue
            compressed = bool(flags & FLAG_COMPRESSED)
            encrypted = bool(flags & FLAG_ENCRYPTED)
            memres = bool(flags & FLAG_MEMRES)
            dir_pos = block_off - dir_size - (16 if memres else 0)
            self.f.seek(dir_pos)
            blob = self.f.read(dir_size)
            if encrypted:
                block_off = next_block
                continue
            if compressed:
                blob = zlib.decompress(blob)
            entries = []
            for i in range(file_count):
                rec = blob[i * DIRENTRY_SIZE:(i + 1) * DIRENTRY_SIZE]
                if len(rec) < DIRENTRY_SIZE:
                    break
                name = rec[:NAME_BYTES].decode("utf-16le", "replace").split("\x00", 1)[0]
                offset, comp, fsize, ts, _u = struct.unpack("<QQQQQ", rec[NAME_BYTES:NAME_BYTES + 40])
                self.f.seek(offset)
                data = self.f.read(comp)
                if compressed:
                    data = zlib.decompress(data)
                entries.append((name, data))
            blocks.append(entries)
            block_off = next_block
        return blocks


# ---------- CLI ----------
def _cmd_list(path):
    with RDAArchive(path) as a:
        n = 0
        for e in a.iter_entries():
            print(f"{e.filesize:>12} {'z' if e.block_compressed else '-'} {e.name}")
            n += 1
        print(f"# {n} entries", file=sys.stderr)


def _cmd_stats(path):
    with RDAArchive(path) as a:
        n = 0
        total_u = 0
        total_c = 0
        exts = {}
        for e in a.iter_entries():
            n += 1
            total_u += e.filesize
            total_c += e.compressed
            ext = e.name.rsplit(".", 1)[-1].lower() if "." in e.name else "(none)"
            exts[ext] = exts.get(ext, 0) + 1
        print(f"archive: {path}")
        print(f"filesize: {a.filesize:,}")
        print(f"firstBlockOffset: 0x{a.first_block_offset:x}")
        print(f"entries: {n:,}")
        print(f"uncompressed total: {total_u:,}")
        print(f"compressed total:   {total_c:,}")
        print("top extensions:")
        for ext, c in sorted(exts.items(), key=lambda x: -x[1])[:20]:
            print(f"  {ext:>8} {c}")


def _cmd_grep(path, substr):
    sub = substr.lower()
    with RDAArchive(path) as a:
        n = 0
        for e in a.iter_entries():
            if sub in e.name.lower():
                print(f"{e.filesize:>12} {'z' if e.block_compressed else '-'} {e.name}")
                n += 1
        print(f"# {n} matches for {substr!r}", file=sys.stderr)


def _cmd_extract(path, substr, outdir):
    sub = substr.lower()
    os.makedirs(outdir, exist_ok=True)
    with RDAArchive(path) as a:
        n = 0
        for e in a.iter_entries():
            if sub in e.name.lower():
                data = a.extract_entry(e)
                rel = e.name.replace("\\", "/")
                dest = os.path.join(outdir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as fo:
                    fo.write(data)
                print(f"extracted {len(data):>12,}  {e.name}")
                n += 1
        print(f"# {n} files extracted to {outdir}", file=sys.stderr)


def main(argv):
    if len(argv) < 3:
        print("usage: rda_reader.py list|stats <rda> | grep <rda> <substr> | "
              "extract <rda> <substr> <out>", file=sys.stderr)
        return 2
    cmd = argv[1]
    rda = argv[2]
    if cmd == "list":
        _cmd_list(rda)
    elif cmd == "stats":
        _cmd_stats(rda)
    elif cmd == "grep":
        _cmd_grep(rda, argv[3])
    elif cmd == "extract":
        _cmd_extract(rda, argv[3], argv[4])
    else:
        print(f"unknown command {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
