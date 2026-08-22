#!/usr/bin/env python3
"""
AC2 CompressedFileData (CFD) writer — produces STORED blocks (no LZO compress).

A CFD is: magic(8) + i16 ver + u8 algo + u16 maxU + u16 maxC + u16 nblocks
          + blockInfo[nblocks] (u16 uncompressedSize, u16 compressedSize)
          + blocks[nblocks] (u32 CRC32 + compressedSize bytes).
A block with uncompressedSize == compressedSize is STORED (read raw) — so we can
re-pack ANY payload without an LZO encoder, just zlib CRC-32 per block.
See ../FORMAT.md. Mirrors AnvilToolkit's DataBlock/CompressedFileData on read.
"""
import struct, zlib

CFD_MAGIC = bytes.fromhex("33aafb5799fa0410")   # 0x1004FA9957FBAA33 (LE)
BLOCK = 32768   # MaxUncompressedBlockSize on this engine


def encode_cfd_stored(data: bytes, algo: int = 2, ver: int = 1) -> bytes:
    """Pack `data` into a CFD using stored (uncompressed) 32 KB blocks."""
    n = (len(data) + BLOCK - 1) // BLOCK or 1
    chunks = [data[i*BLOCK:(i+1)*BLOCK] for i in range(n)]
    out = bytearray()
    out += CFD_MAGIC
    out += struct.pack("<h", ver)
    out += bytes([algo])
    out += struct.pack("<H", BLOCK)            # MaxUncompressedBlockSize
    out += struct.pack("<H", BLOCK)            # MaxCompressedBlockSize
    out += struct.pack("<H", n)                # blockCount
    for c in chunks:                           # blockInfo: (usz, csz) -- equal = stored
        out += struct.pack("<HH", len(c), len(c))
    for c in chunks:                           # blocks: crc + raw
        out += struct.pack("<I", zlib.crc32(c) & 0xFFFFFFFF)
        out += c
    return bytes(out)


def parse_one_cfd(d: bytes, pos: int):
    """Return (decompressed_bytes, end_pos) for the CFD at pos.
    Stored blocks only need no LZO; compressed blocks delegate to ac2_lzo."""
    assert d[pos:pos+8] == CFD_MAGIC
    p = pos + 8
    _ver = struct.unpack_from("<h", d, p)[0]; p += 2
    algo = d[p]; p += 1
    p += 4                                      # maxU, maxC
    nb = struct.unpack_from("<H", d, p)[0]; p += 2
    info = [struct.unpack_from("<HH", d, p + i*4) for i in range(nb)]; p += nb*4
    out = bytearray()
    for (usz, csz) in info:
        p += 4                                  # crc
        cd = d[p:p+csz]; p += csz
        if usz == csz:
            out += cd
        else:
            import ac2_lzo
            out += ac2_lzo.decompress_block(algo, cd, usz)
    return bytes(out), p
