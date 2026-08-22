#!/usr/bin/env python3
r"""
psarc.py — read-only reader for Naughty Dog "The Last of Us Part I" PSARC v1.4
archives (Oodle-compressed). Pure-Python; the ONLY native dependency is the
game's own oo2core_9_win64.dll via oodle.Oodle.

PSARC v1.4 layout (big-endian):
  header (32 bytes)
    0x00  magic "PSAR"
    0x04  u16 verMajor, 0x06 u16 verMinor            (0001 0004 = 1.4)
    0x08  4  compression id  ("oodl" / "zlib" / "lzma")
    0x0C  u32 totalTOCSize   (header + entries + block-size-table)
    0x10  u32 tocEntrySize   (30)
    0x14  u32 numFiles       (incl. entry 0 = the path manifest)
    0x18  u32 blockSize      (0x10000)
    0x1C  u32 archiveFlags
  TOC entries  (numFiles x 30):
    16  md5(path)   (entry 0 hash = all-zero; it is the manifest)
    4   u32 blockListStart   (index into the block-size table)
    5   u40 originalSize      (uncompressed length)
    5   u40 startOffset       (byte offset into the archive)
  block-size table:
    (totalTOCSize - 32 - numFiles*30) / nb entries, each `nb` bytes BE, where nb
    is the smallest count with 256**nb >= blockSize.  A table value of 0 means a
    full raw block of blockSize bytes; a value < min(blockSize,remaining) means an
    Oodle-compressed block; a value == that remainder means a stored (raw) block.

Entry 0 (manifest) decompresses to a newline-separated list of the real paths for
entries 1..numFiles-1 (PSARC stores only md5 name-hashes, not the strings).

CLI:
    python psarc.py info    <a.psarc>
    python psarc.py list    <a.psarc> [--grep PAT]
    python psarc.py extract <a.psarc> <path-substring> [--out FILE]
"""
import os
import sys
import struct
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oodle import Oodle   # noqa: E402


def _u40(b):  # 5-byte big-endian
    return int.from_bytes(b, "big")


def _block_nbytes(block_size):
    nb = 1
    while (1 << (nb * 8)) < block_size:
        nb += 1
    return nb


class Entry:
    __slots__ = ("index", "name_hash", "block_start", "orig_size", "offset", "path")

    def __init__(self, index, name_hash, block_start, orig_size, offset):
        self.index = index
        self.name_hash = name_hash
        self.block_start = block_start
        self.orig_size = orig_size
        self.offset = offset
        self.path = None


class Psarc:
    def __init__(self, path, oodle=None):
        self.path = path
        self.f = open(path, "rb")
        self.oodle = oodle or Oodle()
        self._parse_header()
        self._parse_toc()
        self._load_manifest()

    # ---- parsing -------------------------------------------------------
    def _parse_header(self):
        h = self.f.read(32)
        if h[:4] != b"PSAR":
            raise ValueError(f"not a PSARC (magic {h[:4]!r})")
        self.ver_major, self.ver_minor = struct.unpack(">HH", h[4:8])
        self.compression = h[8:12].decode("ascii", "replace")
        (self.total_toc_size, self.toc_entry_size, self.num_files,
         self.block_size, self.archive_flags) = struct.unpack(">IIIII", h[12:32])
        self.block_nbytes = _block_nbytes(self.block_size)

    def _parse_toc(self):
        raw = self.f.read(self.num_files * self.toc_entry_size)
        self.entries = []
        for i in range(self.num_files):
            e = raw[i * 30:(i + 1) * 30]
            name_hash = e[0:16]
            block_start = struct.unpack(">I", e[16:20])[0]
            orig_size = _u40(e[20:25])
            offset = _u40(e[25:30])
            self.entries.append(Entry(i, name_hash, block_start, orig_size, offset))
        # block-size table fills the rest of the TOC region
        table_bytes = self.total_toc_size - 32 - self.num_files * 30
        tb = self.f.read(table_bytes)
        nb = self.block_nbytes
        self.block_table = [int.from_bytes(tb[j:j + nb], "big")
                            for j in range(0, len(tb), nb)]

    def _read_entry(self, e):
        """Decompress one entry to bytes."""
        self.f.seek(e.offset)
        out = bytearray()
        remaining = e.orig_size
        bi = e.block_start
        while remaining > 0:
            csize = self.block_table[bi]
            bi += 1
            rawlen = min(self.block_size, remaining)
            if csize == 0:                       # full raw block of blockSize
                chunk = self.f.read(self.block_size)
                out += chunk[:rawlen]
            else:
                chunk = self.f.read(csize)
                if csize >= rawlen:              # stored raw (incompressible)
                    out += chunk[:rawlen]
                else:                            # Oodle-compressed
                    out += self.oodle.decompress(chunk, rawlen)
            remaining -= rawlen
        return bytes(out)

    def _load_manifest(self):
        import hashlib
        data = self._read_entry(self.entries[0])
        # ND PSARC delimits manifest paths with NUL (\x00), not newline.
        sep = b"\x00" if b"\x00" in data else b"\n"
        paths = [p.decode("utf-8", "replace").strip()
                 for p in data.split(sep) if p.strip()]
        self.manifest = paths
        # CRITICAL: TOC entries are ordered by md5(path) ascending, NOT by
        # manifest order — so assign each path to the entry whose 16-byte
        # name-hash equals md5(path).  (A naive positional map mislabels
        # nearly every file, e.g. a text path resolving to an sfx audio entry.)
        by_hash = {e.name_hash: e for e in self.entries[1:]}
        self.by_path = {}
        for p in paths:
            e = by_hash.get(hashlib.md5(p.encode("utf-8")).digest())
            if e is not None:
                e.path = p
                self.by_path[p] = e

    # ---- public --------------------------------------------------------
    def files(self):
        return [e for e in self.entries[1:] if e.path]

    def find(self, needle):
        n = needle.lower()
        return [e for e in self.files() if n in (e.path or "").lower()]

    def extract(self, entry):
        return self._read_entry(entry)


def _cmd_info(args):
    p = Psarc(args.archive)
    print(f"path        : {args.archive}")
    print(f"version     : {p.ver_major}.{p.ver_minor}")
    print(f"compression : {p.compression}")
    print(f"numFiles    : {p.num_files}  (incl. manifest)")
    print(f"blockSize   : 0x{p.block_size:x}  (nbytes/block={p.block_nbytes})")
    print(f"archiveFlags: {p.archive_flags}")
    print(f"totalTOCSize: {p.total_toc_size}   blockTableEntries: {len(p.block_table)}")
    sizes = sorted(p.files(), key=lambda e: e.orig_size, reverse=True)
    print("\nlargest entries:")
    for e in sizes[:15]:
        print(f"  {e.orig_size:>12,}  {e.path}")


def _cmd_list(args):
    p = Psarc(args.archive)
    ents = p.find(args.grep) if args.grep else p.files()
    for e in ents:
        print(f"{e.orig_size:>12,}  {e.path}")
    print(f"\n[{len(ents)} entries]", file=sys.stderr)


def _cmd_extract(args):
    p = Psarc(args.archive)
    hits = p.find(args.path)
    if not hits:
        print(f"no entry matching {args.path!r}", file=sys.stderr)
        sys.exit(1)
    if len(hits) > 1 and not args.out:
        for e in hits:
            print(f"  {e.orig_size:>12,}  {e.path}")
        print(f"[{len(hits)} matches — refine, or pass --out to take the first]", file=sys.stderr)
        sys.exit(1)
    e = hits[0]
    data = p.extract(e)
    out = args.out or (os.path.basename(e.path) or f"entry_{e.index}")
    with open(out, "wb") as fh:
        fh.write(data)
    print(f"wrote {len(data):,} bytes -> {out}  (from {e.path})")


def main():
    ap = argparse.ArgumentParser(description="TLOU Part I PSARC reader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("info");    a.add_argument("archive")
    a = sub.add_parser("list");    a.add_argument("archive"); a.add_argument("--grep")
    a = sub.add_parser("extract"); a.add_argument("archive"); a.add_argument("path"); a.add_argument("--out")
    args = ap.parse_args()
    {"info": _cmd_info, "list": _cmd_list, "extract": _cmd_extract}[args.cmd](args)


if __name__ == "__main__":
    main()
