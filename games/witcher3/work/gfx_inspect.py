"""Inspect the Scaleform GFx inside a TW3 .redswf (CR2W -> CFX(zlib) -> GFx tags)."""
import sys, struct, zlib

SWF_TAGS = {48: "DefineFont2", 75: "DefineFont3", 62: "DefineFontInfo2", 13: "DefineFontInfo",
            88: "DefineFontName", 73: "DefineFontAlignZones", 20: "DefineBitsLossless",
            0: "End", 69: "FileAttributes", 77: "Metadata", 43: "FrameLabel",
            91: "DefineFont4", 90: "DefineScalingGrid"}


def find_cfx(data):
    i = data.find(b"CFX")
    if i < 0:
        i = data.find(b"GFX")
    return i


def decompress_gfx(redswf_bytes):
    i = find_cfx(redswf_bytes)
    assert i >= 0, "no CFX/GFX magic"
    magic = redswf_bytes[i:i+3]
    version = redswf_bytes[i+3]
    uncomp = struct.unpack_from("<I", redswf_bytes, i+4)[0]
    body = redswf_bytes[i+8:]
    if magic == b"CFX":
        gfx = b"GFX" + bytes([version]) + struct.pack("<I", uncomp) + zlib.decompress(body)
    else:
        gfx = redswf_bytes[i:i+uncomp]
    return gfx, version, uncomp


def list_tags(gfx):
    # GFx header: "GFX"/"GFC" + version + u32 fileLength, then RECT + u16 frameRate + u16 frameCount
    p = 8
    # skip RECT (frame size): nbits in first 5 bits
    nbits = gfx[p] >> 3
    total_bits = 5 + nbits * 4
    p += (total_bits + 7) // 8
    p += 4  # frameRate(2) + frameCount(2)
    tags = []
    while p < len(gfx):
        if p + 2 > len(gfx):
            break
        code_len = struct.unpack_from("<H", gfx, p)[0]
        p += 2
        code = code_len >> 6
        length = code_len & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", gfx, p)[0]
            p += 4
        tags.append((code, length, p))
        if code == 0:
            break
        p += length
    return tags


def font_glyph_ranges(gfx, code, length, body_off):
    """For DefineFont2/3, read fontID + glyph count + codetable (unicode) to get coverage."""
    b = gfx
    p = body_off
    font_id = struct.unpack_from("<H", b, p)[0]; p += 2
    flags = b[p]; p += 1
    lang = b[p]; p += 1
    name_len = b[p]; p += 1
    name = b[p:p+name_len].decode("latin-1", "replace"); p += name_len
    wide_offsets = bool(flags & 0x08)
    wide_codes = bool(flags & 0x04)
    num_glyphs = struct.unpack_from("<H", b, p)[0]; p += 2
    # offset table
    if wide_offsets:
        p_after_offsets = p + (num_glyphs + 1) * 4
    else:
        p_after_offsets = p + (num_glyphs + 1) * 2
    # code table sits after the glyph shapes; too complex to walk shapes here.
    return {"font_id": font_id, "name": name, "num_glyphs": num_glyphs,
            "wide_codes": wide_codes, "flags": flags, "lang": lang}


if __name__ == "__main__":
    path = sys.argv[1]
    data = open(path, "rb").read()
    gfx, ver, uncomp = decompress_gfx(data)
    print(f"{path}: GFx v{ver} uncomp={uncomp} actual={len(gfx)}")
    tags = list_tags(gfx)
    from collections import Counter
    c = Counter(t[0] for t in tags)
    print("tags:", {SWF_TAGS.get(k, k): v for k, v in c.items()})
    for code, length, off in tags:
        if code in (48, 75):  # DefineFont2/3
            info = font_glyph_ranges(gfx, code, length, off)
            print(f"  {SWF_TAGS[code]} id={info['font_id']} name={info['name']!r} "
                  f"glyphs={info['num_glyphs']} wide_codes={info['wide_codes']} len={length}")
        elif code == 88:  # DefineFontName
            b = gfx[off:off+length]
            fid = struct.unpack_from("<H", b, 0)[0]
            rest = b[2:].split(b"\x00")
            print(f"  DefineFontName id={fid} name={rest[0].decode('latin-1','replace')!r} "
                  f"copyright={rest[1].decode('latin-1','replace') if len(rest)>1 else ''!r}")
