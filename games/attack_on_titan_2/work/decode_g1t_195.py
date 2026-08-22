"""Decode LINKDATA_PLATFORM_DX11.BIN entry 195 -- 150 x 256x256 BC1 textures,
the strongest glyph-atlas candidate found by scan_g1t_small.py -- into real
PNGs (via a minimal DDS wrapper + Pillow's built-in DXT1 decoder, same trick
used earlier for the KSLT BC3 icon atlas) and a montage contact sheet for
visual inspection.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from aot2_linkdata import LinkData  # noqa: E402

from PIL import Image

G1T_MAGIC = b"GT1G"
ARCHIVE = Path("F:/Games/Attack on Titan 2/LINKDATA/LINKDATA_PLATFORM_DX11.BIN")
ENTRY = 195
OUT = Path(__file__).resolve().parent / "g1t195_out"
OUT.mkdir(exist_ok=True)


def dds_header(width, height, fourcc, linear_size):
    # minimal 128-byte DDS header (magic "DDS " + 124-byte DDS_HEADER)
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE
    pf_flags = 0x4  # DDPF_FOURCC
    caps = 0x1000  # DDSCAPS_TEXTURE
    hdr = struct.pack(
        "<4sIIIIIIII44xIIIIIIII4x",
        b"DDS ", 124, flags, height, width, linear_size, 0, 1, 0,
        # 11 reserved dwords skipped via 44x above
        32, pf_flags, *struct.unpack("<I", fourcc), 0, 0, 0, 0,
        # DDPF: size, flags, fourcc, RGBBitCount, masks... simplified below
    )
    return hdr


def make_dds_bc1(width, height, data):
    """Build a minimal valid DDS file wrapping raw BC1 (DXT1) block data."""
    block_bytes = 8  # BC1 = 8 bytes / 4x4 block
    linear_size = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_bytes
    header = bytearray(128)
    struct.pack_into("<4s", header, 0, b"DDS ")
    struct.pack_into("<I", header, 4, 124)  # header size
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    struct.pack_into("<I", header, 8, flags)
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 20, linear_size)
    struct.pack_into("<I", header, 24, 0)  # depth
    struct.pack_into("<I", header, 28, 1)  # mipmapcount
    # pixelformat @ offset 76, size 32
    struct.pack_into("<I", header, 76, 32)  # pf size
    struct.pack_into("<I", header, 80, 0x4)  # DDPF_FOURCC
    struct.pack_into("<4s", header, 84, b"DXT1")
    struct.pack_into("<I", header, 108, 0x1000)  # caps
    return bytes(header) + data[:linear_size]


def parse_g1t_full(buf: bytes):
    table_offset, count, _system, _unk2 = struct.unpack_from("<iiii", buf, 12)
    offsets = struct.unpack_from(f"<{count}i", buf, table_offset)
    out = []
    for i in range(count):
        hdr_pos = table_offset + offsets[i]
        packed_info, ttype, packed_dims, u1, u2, u3, u4, extra_ver = struct.unpack_from(
            "<BBBBBBBB", buf, hdr_pos
        )
        w_exp = packed_dims & 0xF
        h_exp = (packed_dims >> 4) & 0xF
        width = 1 << w_exp
        height = 1 << h_exp
        # image bytes start right after the 8-byte TextureDataHeader; if
        # extra_ver>0 there's a TextureDataHeaderExtended sitting between the
        # header and pixel data (size field-prefixed, per G1TextureGroup.cs)
        img_start = hdr_pos + 8
        if extra_ver > 0:
            (extra_size,) = struct.unpack_from("<I", buf, img_start)
            img_start += extra_size
        next_off = offsets[i + 1] - offsets[i] if i + 1 < count else len(buf) - table_offset - offsets[i]
        img_end = table_offset + offsets[i] + next_off
        out.append((width, height, ttype, extra_ver, buf[img_start:img_end]))
    return out


ld = LinkData(ARCHIVE)
buf = ld.read(ENTRY)
assert buf[0:4] == G1T_MAGIC
textures = parse_g1t_full(buf)
print(f"parsed {len(textures)} textures")

decoded = []
for i, (w, h, ttype, extra_ver, imgdata) in enumerate(textures):
    if ttype != 0x59:  # BC1
        print(f"  [{i}] unexpected type 0x{ttype:x}, skip")
        continue
    try:
        dds = make_dds_bc1(w, h, imgdata)
        im = Image.open(__import__("io").BytesIO(dds))
        im.load()
        decoded.append((i, im.convert("RGBA")))
    except Exception as e:
        print(f"  [{i}] decode failed: {e}")

print(f"decoded {len(decoded)} images")
for i, im in decoded[:20]:
    im.save(OUT / f"tex_{i:03d}.png")

# contact sheet: 15 columns
if decoded:
    cols = 15
    rows = (len(decoded) + cols - 1) // cols
    cell = 64
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (30, 30, 30, 255))
    for idx, (i, im) in enumerate(decoded):
        thumb = im.resize((cell, cell))
        r, c = divmod(idx, cols)
        sheet.paste(thumb, (c * cell, r * cell))
    sheet.save(OUT / "_contact_sheet.png")
    print(f"contact sheet -> {OUT / '_contact_sheet.png'} ({cols}x{rows} grid)")
