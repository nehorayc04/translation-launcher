#!/usr/bin/env python3
r"""
psarc_write.py - surgical PSARC v1.4 (Oodle) repacker for The Last of Us Part I.

Rebuilds an archive with a few entries replaced, WITHOUT recompressing the rest:
every unchanged entry's compressed blocks are stream-copied verbatim from the
source; only the replaced entries are Oodle-compressed. The TOC (md5-ordered,
unchanged order) + block table + offsets are rebuilt. No whole-archive checksum
exists in PSARC, and name-hashes are md5(PATH) (content-independent), so a faithful
rebuild loads (ndarc-style repacks are proven on this game).

    repack(src_psarc, {path: new_bytes, ...}, out_psarc, oodle)

CLI (thin): python psarc_write.py <src> <out> <path=file> [<path=file> ...]
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from psarc import Psarc          # noqa: E402
from oodle import Oodle          # noqa: E402


def _u40(v):
    return v.to_bytes(5, "big")


def _compress_entry(data, oodle, block_size):
    """-> (table_values[list[int]], compressed_bytes, orig_size)."""
    table, blob = [], bytearray()
    if not data:
        return table, b"", 0
    for i in range(0, len(data), block_size):
        raw = data[i:i + block_size]
        rawlen = len(raw)
        comp = oodle.compress(raw)
        if len(comp) < rawlen:            # compressed helps
            table.append(len(comp))
            blob += comp
        else:                             # store raw (0 == full blockSize block)
            table.append(0 if rawlen == block_size else rawlen)
            blob += raw
    return table, bytes(blob), len(data)


def _entry_plan(ps, e, replacements, oodle):
    """Per-entry (table_values, source) where source is ('copy',off,len) or ('new',bytes)."""
    bs = ps.block_size
    if e.path in replacements:
        table, blob, orig = _compress_entry(replacements[e.path], oodle, bs)
        return table, ("new", blob), orig
    nblocks = 0 if e.orig_size == 0 else (e.orig_size + bs - 1) // bs
    table = ps.block_table[e.block_start:e.block_start + nblocks]
    clen = sum(v if v != 0 else bs for v in table)
    return table, ("copy", e.offset, clen), e.orig_size


def repack(src_path, replacements, out_path, oodle=None, progress=True):
    oodle = oodle or Oodle()
    ps = Psarc(src_path, oodle)
    bs = ps.block_size
    nb = ps.block_nbytes
    n = ps.num_files
    ents = ps.entries              # entry 0 = manifest, kept in md5 order

    # sanity: every replacement path must exist
    for p in replacements:
        if p not in ps.by_path:
            raise KeyError(f"replacement path not in archive: {p}")

    # 1) plan every entry
    plans = []
    new_block_table = []
    for e in ents:
        table, source, orig = _entry_plan(ps, e, replacements, oodle)
        plans.append([e, table, source, orig, None, None])   # +blockStart +offset

    # 2) assign blockStart (entry order) and data offsets (write order = entry order)
    total_toc = 32 + n * 30 + len(_flatten(plans)) * nb
    bstart = 0
    off = total_toc
    for pl in plans:
        e, table, source, orig, _, _ = pl
        pl[4] = bstart
        pl[5] = off
        bstart += len(table)
        clen = len(source[1]) if source[0] == "new" else source[2]
        off += clen
        new_block_table.extend(table)

    # 3) write
    with open(src_path, "rb") as src, open(out_path, "wb") as out:
        header = bytearray(src.read(32))
        struct.pack_into(">I", header, 12, total_toc)   # patch totalTOCSize
        out.write(header)
        # TOC
        for pl in plans:
            e, table, source, orig, bstart_i, off_i = pl
            out.write(e.name_hash)                      # 16
            out.write(struct.pack(">I", bstart_i))      # 4  blockListStart
            out.write(_u40(orig))                       # 5  origSize
            out.write(_u40(off_i))                      # 5  startOffset
        # block table
        bt = bytearray()
        for v in new_block_table:
            bt += v.to_bytes(nb, "big")
        out.write(bt)
        assert out.tell() == total_toc, (out.tell(), total_toc)
        # data (entry order)
        done = 0
        for pl in plans:
            e, table, source, orig, _, _ = pl
            if source[0] == "new":
                out.write(source[1])
            else:
                _, o, clen = source
                src.seek(o)
                remaining = clen
                while remaining > 0:
                    chunk = src.read(min(1 << 20, remaining))
                    if not chunk:
                        raise IOError(f"short read for {e.path}")
                    out.write(chunk)
                    remaining -= len(chunk)
            done += 1
            if progress and done % 2000 == 0:
                print(f"  ... {done}/{n} entries")
    return out_path


def _flatten(plans):
    return [v for pl in plans for v in pl[1]]


def main():
    if len(sys.argv) < 4:
        print("usage: psarc_write.py <src.psarc> <out.psarc> <archive/path=localfile> ...")
        sys.exit(2)
    src, out = sys.argv[1], sys.argv[2]
    repl = {}
    for kv in sys.argv[3:]:
        path, local = kv.split("=", 1)
        with open(local, "rb") as f:
            repl[path] = f.read()
    repack(src, repl, out)
    print(f"wrote {out}  ({os.path.getsize(out):,} B)  replaced {len(repl)}")


if __name__ == "__main__":
    main()
