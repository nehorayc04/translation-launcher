"""Scan LINKDATA archives for G1T (TextureGroup) resources and report every
texture's dimensions, sorted by area ascending -- a compact ASCII/Latin
character-atlas would be a SMALL texture, and the prior "visual inspection"
pass in FEASIBILITY.md gate 5 explicitly says "every LARGE G1T texture" --
small ones were never looked at. Metadata-only (no pixel decode) so this is
cheap even across many archives.

Struct layout from Cethleann.Graphics.G1TextureGroup / the Texture/* structs
(fetched fresh 2026-08-10, see _G1TextureGroup.cs, _TextureGroupHeader.cs,
_TextureDataHeader.cs, _TextureDataHeaderExtended.cs, _TexturePackedSize.cs,
_TexturePackedInfo.cs, _TextureType.cs, _TextureUsage.cs in this directory):

    ResourceSectionHeader (12B): u32 magic, i32 version, i32 size
    TextureGroupHeader   (16B): i32 table_offset, i32 count, i32 system, i32 unk2
    usage[count]          (4B each): i32 (TextureUsage enum)
    -- at table_offset --
    offsets[count]        (4B each): i32, relative to table_offset
    -- per texture, at table_offset+offsets[i] --
    TextureDataHeader     (8B): u8 packed_info, u8 type, u8 packed_dims,
                                 u8 u1, u8 u2, u8 u3, u8 u4, u8 extra_ver
        packed_dims: width_exp = low nibble, height_exp = high nibble
                     width = 2**width_exp, height = 2**height_exp
        packed_info: unknown = low nibble, mips = high nibble
    if extra_ver > 0: TextureDataHeaderExtended follows with an explicit
        Width/Height override (u8 offset 8 = a u32 size then the 20-byte
        struct) -- not needed for a first metadata pass, flagged separately.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from aot2_linkdata import LinkData, MAGIC  # noqa: E402

G1T_MAGIC = b"GT1G"  # 'G'<<24|'1'<<16|'T'<<8|'G'<<0, little-endian on disk

TEXTYPE_NAMES = {
    0x1: "R8G8B8A8",
    0x2: "B8G8R8A8",
    0x56: "ETC1",
    0x59: "BC1",
    0x5B: "BC5",
    0x5E: "BC6",
    0x6F: "BrokenETC1",
}

GAME = Path("F:/Games/Attack on Titan 2/LINKDATA")
ARCHIVES = [
    GAME / "REGION" / "LINKDATA_REGION_EU.BIN",
    GAME / "REGION" / "LINKDATA_REGION_EDEN_EU.BIN",
    GAME / "LINKDATA_PLATFORM_DX11.BIN",
    GAME / "LINKDATA_PLATFORM_EDEN_DX11.BIN",
]


def parse_g1t_meta(buf: bytes):
    """Returns a list of (width, height, type_byte, extra_ver) or None if buf
    doesn't parse as a structurally sane G1T."""
    if len(buf) < 28 or buf[0:4] != G1T_MAGIC:
        return None
    try:
        table_offset, count, _system, _unk2 = struct.unpack_from("<iiii", buf, 12)
    except struct.error:
        return None
    if count <= 0 or count > 100_000:
        return None
    off_arr_start = table_offset
    if off_arr_start < 0 or off_arr_start + count * 4 > len(buf):
        return None
    offsets = struct.unpack_from(f"<{count}i", buf, off_arr_start)
    out = []
    for i, o in enumerate(offsets):
        hdr_pos = table_offset + o
        if hdr_pos < 0 or hdr_pos + 8 > len(buf):
            out.append(None)
            continue
        packed_info, ttype, packed_dims, u1, u2, u3, u4, extra_ver = struct.unpack_from(
            "<BBBBBBBB", buf, hdr_pos
        )
        w_exp = packed_dims & 0xF
        h_exp = (packed_dims >> 4) & 0xF
        if w_exp > 16 or h_exp > 16:
            out.append(None)
            continue
        width = 1 << w_exp
        height = 1 << h_exp
        out.append((width, height, ttype, extra_ver))
    return out


def scan_archive(path: Path):
    print(f"=== {path.name} ({path.stat().st_size:,} bytes) ===")
    try:
        ld = LinkData(path)
    except Exception as e:
        print(f"  LinkData open failed: {e}")
        return []
    print(f"  {len(ld.entries)} entries, mult={ld.mult}")
    results = []
    for i in range(len(ld.entries)):
        eo, epad, csize, dsize = ld.entries[i]
        if csize == 0:
            continue
        try:
            buf = ld.read(i)
        except Exception:
            continue
        if len(buf) < 4 or buf[0:4] != G1T_MAGIC:
            continue
        meta = parse_g1t_meta(buf)
        if meta is None:
            continue
        for ti, t in enumerate(meta):
            if t is None:
                continue
            w, h, ttype, extra_ver = t
            results.append((path.name, i, ti, w, h, ttype, extra_ver, len(meta)))
    return results


all_results = []
for p in ARCHIVES:
    if not p.exists():
        print(f"=== {p.name} : MISSING ===")
        continue
    all_results += scan_archive(p)

print(f"\ntotal G1T textures found across all scanned archives: {len(all_results)}")
all_results.sort(key=lambda r: r[3] * r[4])  # area ascending
print("\nSmallest 60 textures (best glyph-atlas candidates):")
print(f"{'archive':<32} {'entry':>6} {'tex#/N':>8} {'W':>5} {'H':>5} {'type':<12} extra_ver")
for name, entry_i, tex_i, w, h, ttype, extra_ver, ntex in all_results[:60]:
    tname = TEXTYPE_NAMES.get(ttype, f"0x{ttype:x}")
    print(f"{name:<32} {entry_i:>6} {tex_i}/{ntex:<6} {w:>5} {h:>5} {tname:<12} {extra_ver}")
