#!/usr/bin/env python3
"""rda_writer.py - minimal WRITER for Anno 1800 "Resource File V2.2" (RDA) archives.

Produces a valid single-block, UNCOMPRESSED archive that Anno reads natively:
    [header 792][file data ...][directory fileCount*560][BlockInfo 32]
The header's firstBlockOffset (@0x310) points at the BlockInfo; BlockInfo.nextBlock
== filesize (terminator). Directory + files are stored uncompressed (block flags=0),
which the reader honours per the block flag. Verified against rda_reader.py round-trip.

Use to rebuild a SMALL rda (e.g. the fan data4.rda = 2 fonts + config) with edited
files, so the game loads them from maindata (the proven mechanism) instead of a loose
mod (whose font override reaches only some atlas contexts).
"""
import struct, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAGIC = b"Resource File V2.2"
HEADER_SIZE = 792            # 0x318
FIRST_BLOCK_OFF_POS = 784    # 0x310
BLOCKINFO_SIZE = 32
DIRENTRY_SIZE = 560
NAME_BYTES = 520


def write_rda_blocks(blocks, out_path):
    """blocks: list of blocks; each block = list of (name_str, data_bytes). Writes an
    uncompressed MULTI-block RDA laid out exactly like Anno's own archives:
      [header][blk1 files][blk1 dir][blk1 BlockInfo][blk2 files][blk2 dir][blk2 BlockInfo]...
    Each block's BlockInfo.nextBlock points at the next block's BlockInfo; the last one's
    nextBlock == filesize (terminator). firstBlockOffset @0x310 points at block 1's BlockInfo."""
    out = bytearray()
    out += MAGIC + b"\x00" * (FIRST_BLOCK_OFF_POS - len(MAGIC))
    out += struct.pack("<Q", 0)                  # firstBlockOffset placeholder (patch after)
    assert len(out) == HEADER_SIZE
    first_block_off = None
    for bi, entries in enumerate(blocks):
        file_section = bytearray()
        dir_records = bytearray()
        file_offset = len(out)                   # files go right here, at the current cursor
        for name, data in entries:
            nb = name.encode("utf-16le")
            if len(nb) > NAME_BYTES:
                raise ValueError(f"name too long: {name}")
            n = len(data)
            dir_records += nb.ljust(NAME_BYTES, b"\x00") + struct.pack("<QQQQQ", file_offset, n, n, 0, 0)
            file_section += data
            file_offset += n
        out += file_section
        out += dir_records                       # directory sits immediately before its BlockInfo
        block_off = len(out)
        if first_block_off is None:
            first_block_off = block_off
        next_block = block_off + BLOCKINFO_SIZE   # provisional; == start of next block's files region...
        # nextBlock must point at the NEXT block's BlockInfo. We don't know it yet, so we compute
        # after all blocks by two-pass. Simpler: append BlockInfo with a placeholder, fix later.
        out += struct.pack("<IIQQQ", 0, len(entries), len(dir_records), len(dir_records), 0)
        # record where this BlockInfo's nextBlock field is: block_off + 24
    # second pass: fix each BlockInfo.nextBlock to point at the following block's BlockInfo,
    # last -> filesize. Re-walk using the reader's own logic.
    filesize = len(out)
    # find the block offsets: walk from first_block_off following provisional nexts won't work
    # because we wrote 0; instead recompute deterministically.
    # Recompute block offsets exactly as written above:
    offs = []
    cur = HEADER_SIZE
    for entries in blocks:
        cur += sum(len(d) for _, d in entries)   # files
        cur += len(entries) * DIRENTRY_SIZE       # directory
        offs.append(cur)                          # BlockInfo position
        cur += BLOCKINFO_SIZE
    assert offs[0] == first_block_off, (offs, first_block_off)
    for i, bo in enumerate(offs):
        nxt = offs[i + 1] if i + 1 < len(offs) else filesize
        struct.pack_into("<Q", out, bo + 24, nxt)  # nextBlock field @ +24
    struct.pack_into("<Q", out, FIRST_BLOCK_OFF_POS, first_block_off)

    with open(out_path, "wb") as f:
        f.write(out)
    return len(out)


def write_rda(entries, out_path):
    """Single-block convenience wrapper."""
    return write_rda_blocks([entries], out_path)


if __name__ == "__main__":
    # self-test: round-trip the fan data4.rda through read -> write -> read
    from rda_reader import RDAArchive
    src = sys.argv[1] if len(sys.argv) > 1 else r"F:/Game Lab/Anno 1800/_Arabic Localization/maindata/data4.rda"
    ents = []
    with RDAArchive(src) as a:
        for e in a.iter_entries():
            ents.append((e.name, a.extract_entry(e)))
    out = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/rda_selftest.rda"
    import os; os.makedirs(os.path.dirname(out), exist_ok=True)
    sz = write_rda(ents, out)
    with RDAArchive(out) as a2:
        got = [(e.name, a2.extract_entry(e)) for e in a2.iter_entries()]
    ok = (len(got) == len(ents)) and all(g == o for g, o in zip(got, ents))
    print(f"wrote {sz:,} B, {len(ents)} entries; round-trip {'OK' if ok else 'MISMATCH'}")
    for (n, d) in got:
        print(f"   {n}  {len(d):,} B")
