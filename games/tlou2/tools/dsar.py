#!/usr/bin/env python3
r"""
dsar.py — read-only reader for The Last of Us Part II Remastered (PC) archives.

Container stack (cracked + validated 2026-07-06):
  OUTER  DSAR  = Naughty Dog "DirectStorage Archive". LZ4-block chunks (usually
                 256 KB uncompressed) that reconstruct a virtual INNER PSARC stream.
  INNER  PSARC = Sony PSARC v1.4, compression id "zlib", 64 KB blocks. Standard
                 30-byte TOC entries keyed by md5(path); entry 0 = NUL-separated
                 path manifest. (Same family as TLOU Part I — see games/tlou1.)

DSAR header (little-endian):
  0x00  char[4] "DSAR"
  0x04  u16 verMajor (3), u16 verMinor (1)
  0x08  u32 numEntries
  0x0C  u32 dataStart     (= 16 + numEntries*32, padded up to 0x20; where LZ4 data begins)
  0x10  u64 totalUncompressedSize  (size of the reconstructed inner PSARC)
  0x18  "PADDING*"...     (pad to 0x20)
DSAR entry (32 bytes) x numEntries, sorted by decompOffset:
  u64 decompOffset   (offset into the virtual inner-PSARC stream)
  u64 compOffset     (byte offset in THIS file where the LZ4 block lives)
  u32 uncompSize     (this chunk's decompressed size)
  u32 compSize       (on-disk size; if == uncompSize the chunk is stored raw)
  u64 flags          (0x5555555555555403 constant here; low byte 0x03 = LZ4/DirectStorage)

Inner PSARC v1.4 (big-endian), same as TLOU1:
  32-byte header: "PSAR" | u16 verMaj,verMin (1,4) | char[4] comp | u32 tocSize
                  | u32 tocEntrySize(30) | u32 numFiles | u32 blockSize | u32 flags
  numFiles x 30-byte TOC entries: 16 md5(path) | u32 blockStart | u40 origSize | u40 offset
  block-size table: (tocSize - 32 - numFiles*30) bytes, `nb`-byte BE values.
  A block value 0 = full raw block of blockSize; value < rawlen = zlib block; == rawlen = stored.

CLI:
  python dsar.py info    <a.psarc>
  python dsar.py list    <a.psarc> [--grep PAT]
  python dsar.py extract <a.psarc> <path-substring> [--out FILE]
"""
import os, sys, struct, zlib, bisect, hashlib, argparse
import lz4.block


# ----------------------------------------------------------------------------
# Layer 1 — DSAR outer container -> virtual inner-PSARC byte stream
# ----------------------------------------------------------------------------
class Dsar:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        hb = self.f.read(24)
        if hb[:4] != b"DSAR":
            raise ValueError(f"not a DSAR (magic {hb[:4]!r})")
        self.ver_major, self.ver_minor = struct.unpack_from("<HH", hb, 4)
        self.num_entries = struct.unpack_from("<I", hb, 8)[0]
        self.data_start = struct.unpack_from("<I", hb, 12)[0]
        self.total_size = struct.unpack_from("<Q", hb, 16)[0]
        self.f.seek(0x20)
        tbl = self.f.read(self.num_entries * 32)
        self.d_off, self.c_off, self.u_size, self.c_size = [], [], [], []
        for i in range(self.num_entries):
            do, co = struct.unpack_from("<QQ", tbl, i * 32)
            us, cs = struct.unpack_from("<II", tbl, i * 32 + 16)
            self.d_off.append(do); self.c_off.append(co)
            self.u_size.append(us); self.c_size.append(cs)

    def read(self, off, length):
        """Read `length` decompressed bytes at virtual offset `off`."""
        out = bytearray()
        i = bisect.bisect_right(self.d_off, off) - 1
        if i < 0:
            i = 0
        pos = off
        n = self.num_entries
        while length > 0 and i < n:
            do = self.d_off[i]
            us = self.u_size[i]
            if do + us <= pos:
                i += 1; continue
            if do > pos:
                raise ValueError(f"gap in DSAR stream at {pos:#x}")
            cs = self.c_size[i]
            self.f.seek(self.c_off[i])
            raw = self.f.read(cs)
            chunk = raw if cs == us else lz4.block.decompress(raw, uncompressed_size=us)
            local = pos - do
            take = min(length, us - local)
            out += chunk[local:local + take]
            pos += take; length -= take; i += 1
        return bytes(out)


# ----------------------------------------------------------------------------
# Layer 2 — inner PSARC v1.4 (zlib), read through the DSAR virtual stream
# ----------------------------------------------------------------------------
def _u40(b):
    return int.from_bytes(b, "big")


def _block_nbytes(block_size):
    nb = 1
    while (1 << (nb * 8)) < block_size:
        nb += 1
    return nb


class Entry:
    __slots__ = ("index", "name_hash", "block_start", "orig_size", "offset", "path")

    def __init__(self, index, name_hash, block_start, orig_size, offset):
        self.index = index; self.name_hash = name_hash
        self.block_start = block_start; self.orig_size = orig_size
        self.offset = offset; self.path = None


class Psarc2:
    """Inner PSARC reader over a Dsar virtual stream. Interface mirrors
    games/tlou1/tools/psarc.py so downstream scripts port unchanged."""

    def __init__(self, path):
        self.path = path
        self.d = Dsar(path)
        self._parse_header()
        self._parse_toc()
        self._load_manifest()

    def _parse_header(self):
        h = self.d.read(0, 32)
        if h[:4] != b"PSAR":
            raise ValueError(f"inner not PSARC (magic {h[:4]!r})")
        self.ver_major, self.ver_minor = struct.unpack(">HH", h[4:8])
        self.compression = h[8:12].decode("ascii", "replace")
        (self.total_toc_size, self.toc_entry_size, self.num_files,
         self.block_size, self.archive_flags) = struct.unpack(">IIIII", h[12:32])
        self.block_nbytes = _block_nbytes(self.block_size)

    def _parse_toc(self):
        raw = self.d.read(32, self.num_files * self.toc_entry_size)
        self.entries = []
        for i in range(self.num_files):
            e = raw[i * 30:(i + 1) * 30]
            self.entries.append(Entry(
                i, e[0:16], struct.unpack(">I", e[16:20])[0],
                _u40(e[20:25]), _u40(e[25:30])))
        table_off = 32 + self.num_files * 30
        table_bytes = self.total_toc_size - table_off
        tb = self.d.read(table_off, table_bytes)
        nb = self.block_nbytes
        self.block_table = [int.from_bytes(tb[j:j + nb], "big")
                            for j in range(0, len(tb), nb)]

    def _read_entry(self, e):
        out = bytearray()
        remaining = e.orig_size
        bi = e.block_start
        pos = e.offset
        while remaining > 0:
            csize = self.block_table[bi]; bi += 1
            rawlen = min(self.block_size, remaining)
            if csize == 0:                          # full raw block
                out += self.d.read(pos, self.block_size)[:rawlen]; pos += self.block_size
            else:
                chunk = self.d.read(pos, csize); pos += csize
                if csize >= rawlen:                 # stored raw
                    out += chunk[:rawlen]
                else:                               # zlib block
                    out += zlib.decompress(chunk)
            remaining -= rawlen
        return bytes(out)

    def _load_manifest(self):
        data = self._read_entry(self.entries[0])
        sep = b"\x00" if b"\x00" in data else b"\n"
        paths = [p.decode("utf-8", "replace").strip()
                 for p in data.split(sep) if p.strip()]
        self.manifest = paths
        by_hash = {e.name_hash: e for e in self.entries[1:]}
        self.by_path = {}
        for p in paths:
            e = by_hash.get(hashlib.md5(p.encode("utf-8")).digest())
            if e is not None:
                e.path = p; self.by_path[p] = e

    def files(self):
        return [e for e in self.entries[1:] if e.path]

    def find(self, needle):
        n = needle.lower()
        return [e for e in self.files() if n in (e.path or "").lower()]

    def extract(self, entry):
        return self._read_entry(entry)


# ----------------------------------------------------------------------------
def _cmd_info(a):
    p = Psarc2(a.archive)
    print(f"path         : {a.archive}")
    print(f"DSAR         : v{p.d.ver_major}.{p.d.ver_minor}  entries={p.d.num_entries}  innerSize={p.d.total_size:,}")
    print(f"inner PSARC  : v{p.ver_major}.{p.ver_minor}  comp={p.compression}  numFiles={p.num_files}")
    print(f"blockSize    : 0x{p.block_size:x}  tocSize=0x{p.total_toc_size:x}  blockTable={len(p.block_table)}")
    big = sorted(p.files(), key=lambda e: e.orig_size, reverse=True)[:15]
    print("\nlargest entries:")
    for e in big:
        print(f"  {e.orig_size:>13,}  {e.path}")


def _cmd_list(a):
    p = Psarc2(a.archive)
    ents = p.find(a.grep) if a.grep else p.files()
    for e in ents:
        print(f"{e.orig_size:>13,}  {e.path}")
    print(f"\n[{len(ents)} entries]", file=sys.stderr)


def _cmd_extract(a):
    p = Psarc2(a.archive)
    hits = p.find(a.path)
    if not hits:
        print(f"no entry matching {a.path!r}", file=sys.stderr); sys.exit(1)
    if len(hits) > 1 and not a.out:
        for e in hits:
            print(f"  {e.orig_size:>13,}  {e.path}")
        print(f"[{len(hits)} matches — refine or pass --out]", file=sys.stderr); sys.exit(1)
    e = hits[0]
    data = p.extract(e)
    out = a.out or (os.path.basename(e.path) or f"entry_{e.index}")
    with open(out, "wb") as fh:
        fh.write(data)
    print(f"wrote {len(data):,} bytes -> {out}  (from {e.path})")


def main():
    ap = argparse.ArgumentParser(description="TLOU Part II Remastered DSAR/PSARC reader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("info");    x.add_argument("archive")
    x = sub.add_parser("list");    x.add_argument("archive"); x.add_argument("--grep")
    x = sub.add_parser("extract"); x.add_argument("archive"); x.add_argument("path"); x.add_argument("--out")
    a = ap.parse_args()
    {"info": _cmd_info, "list": _cmd_list, "extract": _cmd_extract}[a.cmd](a)


if __name__ == "__main__":
    main()
