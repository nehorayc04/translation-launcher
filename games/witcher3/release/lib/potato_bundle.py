#!/usr/bin/env python3
"""Pure-Python reader/extractor for The Witcher 3 "POTATO70" .bundle archives.
Format from hhrhhr/Lua-utils-for-Witcher-3 (unpack_potato.lua), verified against the game files.

Header: magic "POTATO70"(8) u32(filesize) u32 size u32 header_sz u32 data_sz str(8)
TOC @0x20, entry = 320 bytes: name[256] str(16) u32(0) u32 size u32 zsize u32 offs u32 u32 str(16) u32 u32 pack
pack: 0=stored, 1=zlib, 2/3=doboz, 4/5=LZ4
"""
import struct, zlib, os


def snappy_compress(data):
    """Minimal valid Snappy compressor: emits literals, RLE-compressing runs of >=4 repeated bytes
    via 1-offset copies (enough to pack the trailing zero-pad so a delta-0 splice fits)."""
    out = bytearray()
    n = len(data)
    v = n
    while True:                                   # preamble varint (uncompressed length)
        b = v & 0x7F; v >>= 7
        out.append(b | 0x80 if v else b)
        if not v:
            break
    lit_start = 0

    def flush_lit(end):
        nonlocal lit_start
        if end <= lit_start:
            return
        L = end - lit_start; ln = L - 1
        if ln < 60:
            out.append(ln << 2)
        else:
            nb = (ln.bit_length() + 7) // 8
            out.append((59 + nb) << 2)
            out.extend(ln.to_bytes(nb, "little"))
        out.extend(data[lit_start:end])
        lit_start = end

    i = 0
    while i < n:
        if i > 0 and data[i] == data[i - 1]:
            j = i
            while j < n and data[j] == data[i - 1]:
                j += 1
            run = j - i
            if run >= 4:
                flush_lit(i)
                r = run
                while r > 0:
                    ln = min(r, 64)
                    out.append(((ln - 1) << 2) | 2)      # copy, 2-byte offset
                    out += (1).to_bytes(2, "little")
                    r -= ln
                i = j; lit_start = i
                continue
        i += 1
    flush_lit(n)
    return bytes(out)


def snappy_decompress(data):
    """Pure-Python Snappy decompressor. TW3 bundle pack==2 is Snappy (varint size + tags),
    NOT doboz (the hhrhhr lua comment is wrong). Verified: fonts_ar starts B9 E3 0E = varint 242105."""
    p = 0
    length = shift = 0
    while True:
        b = data[p]; p += 1
        length |= (b & 0x7F) << shift
        if b < 0x80:
            break
        shift += 7
    out = bytearray()
    n = len(data)
    while p < n and len(out) < length:      # stop at uncompressed size (ignore trailing pad)
        tag = data[p]; p += 1
        t = tag & 3
        if t == 0:                       # literal
            ln = tag >> 2
            if ln >= 60:
                nb = ln - 59
                ln = int.from_bytes(data[p:p + nb], "little"); p += nb
            ln += 1
            out += data[p:p + ln]; p += ln
        else:
            if t == 1:                   # copy, 1-byte offset
                ln = 4 + ((tag >> 2) & 7)
                offset = ((tag >> 5) << 8) | data[p]; p += 1
            elif t == 2:                 # copy, 2-byte offset
                ln = 1 + (tag >> 2)
                offset = int.from_bytes(data[p:p + 2], "little"); p += 2
            else:                        # copy, 4-byte offset
                ln = 1 + (tag >> 2)
                offset = int.from_bytes(data[p:p + 4], "little"); p += 4
            start = len(out) - offset
            for k in range(ln):          # byte-by-byte (handles overlap)
                out.append(out[start + k])
    return bytes(out)


def list_entries(path):
    d = open(path, "rb").read()
    assert d[:8] == b"POTATO70", "not a POTATO70 bundle"
    header_sz = struct.unpack_from("<I", d, 0x10)[0]
    n = header_sz // 320
    entries = []
    for i in range(n):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        size, zsize, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pack = struct.unpack_from("<I", d, base + 320 - 4)[0]
        entries.append({"name": name, "size": size, "zsize": zsize, "offs": offs, "pack": pack})
    return d, entries


def extract(d, e):
    raw = d[e["offs"]:e["offs"] + e["zsize"]]
    if e["pack"] == 0:
        return raw
    if e["pack"] == 1:
        return zlib.decompress(raw)
    if e["pack"] in (2, 3):
        return snappy_decompress(raw)          # TW3 pack 2/3 = Snappy
    if e["pack"] in (4, 5):
        import lz4.block
        return lz4.block.decompress(raw, uncompressed_size=e["size"])
    raise NotImplementedError(f"pack={e['pack']} for {e['name']}")


if __name__ == "__main__":
    import sys
    GAME = r"D:\Games\The Witcher 3 - Complete Edition"
    bundle = sys.argv[1] if len(sys.argv) > 1 else os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
    filt = sys.argv[2] if len(sys.argv) > 2 else "font"
    d, entries = list_entries(bundle)
    print(f"{os.path.basename(bundle)}: {len(entries)} files")
    for e in entries:
        if filt.lower() in e["name"].lower():
            print(f"  pack={e['pack']} size={e['size']:>9} zsize={e['zsize']:>9} off={e['offs']:>10}  {e['name']}")
