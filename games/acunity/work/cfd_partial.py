"""Partial CFD re-LZO: keep every original compressed block verbatim, recompress ONLY the
blocks whose uncompressed range overlaps a changed region. Guarantees on-disk <= original
when the changed regions shrank (our padded-smaller fonts)."""
import struct, zlib
import lzallright
_MAGIC = 0x1004FA9957FBAA33
_C = lzallright.LZOCompressor()


def parse_cfd(data, pos):
    assert struct.unpack_from("<Q", data, pos)[0] == _MAGIC
    start = pos
    pos += 8
    compinfo7 = data[pos:pos + 7]
    pos += 7
    n = struct.unpack_from("<i", data, pos)[0]
    pos += 4
    bi = pos
    pos += n * 4
    blocks = []
    uc = 0
    for k in range(n):
        u, c = struct.unpack_from("<HH", data, bi + k * 4)
        pos += 4  # crc
        comp = data[pos:pos + c]
        pos += c
        blocks.append([uc, u, comp])   # [uncomp_start, uncomp_len, orig_comp_bytes]
        uc += u
    return start, pos, compinfo7, blocks   # pos = end of this CFD


def rebuild_partial(compinfo7, blocks, new_content, changed):
    """changed = list of (start,end) uncomp ranges that were modified."""
    def overlaps(u0, u1):
        return any(not (u1 <= s or u0 >= e) for s, e in changed)
    newblocks = []   # (uncomp_len, comp_bytes)
    for uc, u, origcomp in blocks:
        if overlaps(uc, uc + u):
            raw = bytes(new_content[uc:uc + u])
            comp = bytes(_C.compress(raw))
            if len(comp) >= u:
                comp = raw                      # store
            newblocks.append((u, comp))
        else:
            newblocks.append((u, origcomp))     # verbatim
    out = bytearray()
    out += struct.pack("<Q", _MAGIC)
    out += compinfo7
    out += struct.pack("<i", len(newblocks))
    for u, comp in newblocks:
        out += struct.pack("<HH", u, len(comp))
    for u, comp in newblocks:
        out += struct.pack("<I", zlib.crc32(comp) & 0xffffffff)
        out += comp
    return bytes(out)
