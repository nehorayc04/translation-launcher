"""
Far Cry 6 OASIS localization codec  (games/farcry6/tools)

The Arabic UI/system text lives in  languages/arabic/oasisstrings.oasis.bin  inside
common.fat/common.dat, stored as FAT scheme-2 (a single standard LZ4 block, decoded
by fc6_fat.read_data).  The decompressed oasis has this layout (reversed from
FCBConverter OasisstringsCompressedFile.cs + the real bytes, cross-checked byte-exact
against the live common.fat -- 26,793 strings, 0 leftover):

  file:
    u32 version = 1
    u32 sectionCount
    [sectionCount x Section]

  Section:
    u32 NameCRC
    u32 StringCount
    [StringCount x { u32 Id, u32 SectionCRC, u32 EnumCRC, u32 Extra(=0xFFFFFFFF) }]  # 16B
    u32 CompressedValuesSectionsCount
    [CompressedValuesSectionsCount x CompressedValues]

  CompressedValues:
    u32 LastSortedCRC
    s32 CompressedSize
    s32 DecompressedSize
    byte[CompressedSize] CompressedBytes      # inner = standard LZ4 block, LZ4Decompressor64 default

  inner decompressed (DecompressedValues), values ORDERED by EnumCRC:
    s32 StringCount
    [StringCount x u32 SortedEnums]
    [StringCount x s32 StringOffsets]
    [StringCount x { u32 id, utf-16le value, u16 0 terminator }]

Editing keeps EVERY untouched section byte-identical (only the sections that own an
edited string are rebuilt), so the on-disk delta is tiny -- safest against integrity
checks.  The inner value blocks are re-emitted as ALL-LITERAL LZ4 (accepted by any
LZ4 decoder; FCBConverter's own compressor is commented out / null).
"""
import struct, lz4.block

MAX_LENGTH = 16384


class _R:
    def __init__(s, d): s.d = d; s.p = 0
    def u32(s): v = struct.unpack_from("<I", s.d, s.p)[0]; s.p += 4; return v
    def s32(s): v = struct.unpack_from("<i", s.d, s.p)[0]; s.p += 4; return v
    def take(s, n): v = s.d[s.p:s.p + n]; s.p += n; return v


def _parse_inner(blob):
    r = _R(blob); sc = r.s32()
    [r.u32() for _ in range(sc)]          # SortedEnums (unused on read; rebuilt on write)
    [r.s32() for _ in range(sc)]          # StringOffsets
    pairs = []
    for _ in range(sc):
        sid = r.u32(); start = r.p
        while struct.unpack_from("<H", r.d, r.p)[0] != 0:
            r.p += 2
        pairs.append((sid, r.d[start:r.p].decode("utf-16-le"))); r.p += 2
    return pairs


class Section:
    __slots__ = ("nameCRC", "strings", "values", "enumById", "start", "end")

    def __init__(self):
        self.strings = []      # [(id, sectionCRC, enumCRC, extra)]
        self.values = {}       # id -> value
        self.enumById = {}     # id -> enumCRC


def parse(data):
    """Return (version, [Section]).  Each Section carries .start/.end byte range in `data`."""
    r = _R(data)
    version = r.u32(); sectionCount = r.u32()
    sections = []
    for _ in range(sectionCount):
        sec = Section(); sec.start = r.p
        sec.nameCRC = r.u32(); strCount = r.u32()
        for _ in range(strCount):
            sid = r.u32(); scrc = r.u32(); ecrc = r.u32(); extra = r.u32()
            sec.strings.append((sid, scrc, ecrc, extra)); sec.enumById[sid] = ecrc
        cvs = r.u32()
        for _ in range(cvs):
            r.u32(); cSize = r.s32(); dSize = r.s32(); cb = r.take(cSize)
            for sid, val in _parse_inner(lz4.block.decompress(cb, uncompressed_size=dSize)):
                sec.values[sid] = val
        sec.end = r.p
        sections.append(sec)
    return version, sections


def _lz4_all_literal(b):
    n = len(b); out = bytearray()
    out.append(0xF0 if n >= 15 else (n << 4))
    if n >= 15:
        rem = n - 15
        while rem >= 255:
            out.append(255); rem -= 255
        out.append(rem)
    return bytes(out) + b


def _build_inner(items):        # items: [(id, enumCRC, value)] already sorted by enumCRC
    out = bytearray(struct.pack("<i", len(items)))
    for sid, ecrc, val in items:
        out += struct.pack("<I", ecrc)
    off = 0
    for sid, ecrc, val in items:
        out += struct.pack("<i", off); off += len(val.encode("utf-16-le")) + 6
    for sid, ecrc, val in items:
        out += struct.pack("<I", sid) + val.encode("utf-16-le") + b"\x00\x00"
    return bytes(out)


def _serialize_section(sec):
    o = bytearray(struct.pack("<II", sec.nameCRC, len(sec.strings)))
    for sid, scrc, ecrc, extra in sec.strings:
        o += struct.pack("<IIII", sid, scrc, ecrc, extra)
    ordered = sorted(sec.strings, key=lambda t: t[2])       # by enumCRC, like the game
    blocks = []; cur = []; num = 0; num2 = 0
    for sid, scrc, ecrc, extra in ordered:
        val = sec.values[sid]
        num += 2 * len(val); cur.append((sid, ecrc, val))
        if num >= MAX_LENGTH and ecrc != num2:
            blocks.append(cur); cur = []; num = 0; num2 = 0
        else:
            num2 = ecrc
    if cur:
        blocks.append(cur)
    o += struct.pack("<I", len(blocks))
    for blk in blocks:
        raw = _build_inner(blk); comp = _lz4_all_literal(raw)
        o += struct.pack("<IiI", blk[-1][1], len(comp), len(raw)) + comp
    return bytes(o)


def edit(data, edits):
    """
    edits: {(sectionCRC, id): new_value}.  Rebuild ONLY the sections that own an edited
    string; every other section is copied byte-for-byte from `data`.  Returns new bytes.
    """
    version, sections = parse(data)
    by_crc = {}
    for (scrc, sid) in edits:
        by_crc.setdefault(scrc, {})[sid] = edits[(scrc, sid)]
    out = bytearray(struct.pack("<II", version, len(sections)))
    applied = 0
    for sec in sections:
        if sec.nameCRC in by_crc:
            for sid, nv in by_crc[sec.nameCRC].items():
                if sid in sec.values:
                    sec.values[sid] = nv; applied += 1
            out += _serialize_section(sec)
        else:
            out += data[sec.start:sec.end]        # untouched -> verbatim
    return bytes(out), applied


# languages\arabic\oasisstrings.oasis.bin  (CRC64, validated against the live common.fat)
OASIS_HASH = 0x14f790b7fb9610c2

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from fc6_fat import Fat
    fat = Fat(sys.argv[1] if len(sys.argv) > 1 else r"F:/Game Lab/Far Cry 6/data_final/pc/common.fat")
    en = fat.by_hash[OASIS_HASH]
    data = fat.read_data(en)
    ver, secs = parse(data)
    tot = sum(len(s.values) for s in secs)
    print(f"oasis ver={ver} sections={len(secs)} strings={tot} bytes={len(data)}")
