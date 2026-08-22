"""
Dunia FAT2 entry (de)compression.
  scheme 0 = stored (raw)
  scheme 2 = Zlib = chunked RAW-DEFLATE (Gibbed DecompressZlib), the real FC6 codec.

Zlib-block layout (from FCBConverter EntryDecompression.DecompressZlib):
  header: 8 x u16 LE.  sizes[0]=blockCount, maxUncBlock = 16*(sizes[1]+1),
          sizes[2..7] = first 6 compressed-block sizes.
  Then, every time the size-cursor hits 8, refill with another 8 x u16.
  Each block: read `compressedBlockSize` bytes -> raw inflate ->
              uncompressedBlockSize (= min(maxUncBlock,left), or `left` on the last block).
              then skip padding = (16 - compressedBlockSize % 16) % 16.
"""
import struct, zlib, io


def decompress_zlib(raw, unc_size):
    inp = io.BytesIO(raw)
    out = bytearray()

    def rd_sizes():
        return list(struct.unpack("<8H", inp.read(16)))

    sizes = rd_sizes()
    block_count = sizes[0]
    max_unc = 16 * (sizes[1] + 1)
    left = unc_size
    c = 2
    for i in range(block_count):
        if c == 8:
            sizes = rd_sizes()
            c = 0
        cbs = sizes[c]; c += 1
        if cbs == 0:
            raise NotImplementedError("zero-size block")
        unc_bs = (min(max_unc, left) if i + 1 < block_count else left)
        cdata = inp.read(cbs)
        d = zlib.decompressobj(-15)  # raw deflate (nowrap)
        chunk = d.decompress(cdata, unc_bs)
        chunk += d.flush()
        out += chunk
        left -= len(chunk)
        pad = (16 - (cbs % 16)) % 16
        if pad:
            inp.seek(pad, io.SEEK_CUR)
    if len(out) != unc_size:
        raise ValueError(f"zlib size mismatch {len(out)} != {unc_size}")
    return bytes(out)
