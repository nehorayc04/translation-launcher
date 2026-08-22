"""
Far Cry 5 OASIS localization codec  (games/farcry5/tools)

FC5 ships NINE text languages at  languages/<lang>/oasisstrings.oasis.bin  inside
common.fat/common.dat AND patch.fat/patch.dat (patch overrides common), stored as
FAT scheme-2 (a single standard LZ4 block, decoded by fc5_fat.read_data).

The container is the SAME family as Far Cry 6's, with exactly ONE difference:

    FC6 string record = 16 bytes  { u32 Id, u32 SectionCRC, u32 EnumCRC, u32 Extra=0xFFFFFFFF }
    FC5 string record = 12 bytes  { u32 Id, u32 SectionCRC, u32 EnumCRC }        <-- no Extra

Everything else is identical:

  file:
    u32 version = 1
    u32 sectionCount
    [sectionCount x Section]

  Section:
    u32 NameCRC
    u32 StringCount
    [StringCount x { u32 Id, u32 SectionCRC, u32 EnumCRC }]            # 12B (FC5)
    u32 CompressedValuesSectionsCount
    [CompressedValuesSectionsCount x CompressedValues]

  CompressedValues:
    u32 LastSortedCRC
    s32 CompressedSize
    s32 DecompressedSize
    byte[CompressedSize] CompressedBytes       # inner = standard LZ4 block

  inner decompressed, values ORDERED by EnumCRC:
    s32 StringCount
    [StringCount x u32 SortedEnums]
    [StringCount x s32 StringOffsets]
    [StringCount x { u32 id, utf-16le value, u16 0 terminator }]

edit() rebuilds ONLY the sections that own an edited string; every other section is
copied byte-for-byte, so the on-disk delta stays tiny (safest against integrity checks).
Inner value blocks are re-emitted as ALL-LITERAL LZ4 (accepted by any LZ4 decoder).
"""
import struct
import lz4.block

MAX_LENGTH = 16384
RECORD_SIZE = 12                      # <-- the ONLY structural delta vs Far Cry 6


class _R:
    def __init__(s, d): s.d = d; s.p = 0
    def u32(s): v = struct.unpack_from("<I", s.d, s.p)[0]; s.p += 4; return v
    def s32(s): v = struct.unpack_from("<i", s.d, s.p)[0]; s.p += 4; return v
    def take(s, n): v = s.d[s.p:s.p + n]; s.p += n; return v


def _parse_inner(blob):
    r = _R(blob); sc = r.s32()
    [r.u32() for _ in range(sc)]          # SortedEnums (rebuilt on write)
    [r.s32() for _ in range(sc)]          # StringOffsets (rebuilt on write)
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
        self.strings = []      # [(id, sectionCRC, enumCRC)]
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
            sid = r.u32(); scrc = r.u32(); ecrc = r.u32()
            sec.strings.append((sid, scrc, ecrc)); sec.enumById[sid] = ecrc
        cvs = r.u32()
        for _ in range(cvs):
            r.u32(); cSize = r.s32(); dSize = r.s32(); cb = r.take(cSize)
            for sid, val in _parse_inner(lz4.block.decompress(cb, uncompressed_size=dSize)):
                sec.values[sid] = val
        sec.end = r.p
        sections.append(sec)
    if r.p != len(data):
        raise ValueError(f"leftover bytes: consumed {r.p} of {len(data)}")
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
    for sid, scrc, ecrc in sec.strings:
        o += struct.pack("<III", sid, scrc, ecrc)
    ordered = sorted(sec.strings, key=lambda t: t[2])       # by enumCRC, like the game
    blocks = []; cur = []; num = 0; num2 = 0
    for sid, scrc, ecrc in ordered:
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
    string; every other section is copied byte-for-byte from `data`.  Returns (bytes, applied).
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


def flat(sections):
    """{(sectionCRC, id): value} across every section."""
    return {(s.nameCRC, sid): v for s in sections for sid, v in s.values.items()}


LANGS = ["english", "arabic", "french", "german", "italian",
         "spanish", "russian", "brazilian", "japanese"]


def oasis_path(lang):
    return f"languages/{lang}/oasisstrings.oasis.bin"


if __name__ == "__main__":
    import sys, os
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fc5_fat import Fat
    from fc5_crc64 import name_hash
    G = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
    fat = Fat(os.path.join(G, "data_final", "pc", "common.fat"))
    for lang in LANGS:
        e = fat.by_hash.get(name_hash(oasis_path(lang)))
        if not e:
            print(f"{lang:10s} absent"); continue
        raw = fat.read_data(e)
        ver, secs = parse(raw)
        vals = flat(secs)
        # identity round-trip: edit with nothing must reproduce the input byte-for-byte
        rebuilt, applied = edit(raw, {})
        print(f"{lang:10s} ver={ver} sections={len(secs):>4} strings={len(vals):>7,} "
              f"bytes={len(raw):>9,}  identity={'BYTE-IDENTICAL' if rebuilt == raw else 'DIFFERS'}")
