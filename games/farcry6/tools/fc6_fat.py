"""
Far Cry 6 Dunia FAT2 v11 archive reader (pure Python, no deps for reading raw
entries; LZO needed only to decompress scheme-2 entries).

Format (cracked 2026-07-24, validated against the real common.fat):
  header:
    @0  u32 magic   = 0x46415432 ("FAT2")
    @4  u32 version = 11               (FC6; FCBConverter only handles <=9)
    @8  u32 platform+flags (1 = PC)    (platform = &0xFF, unknown = >>8)
    @12 u32 unknown = 0                (NEW in v11 vs v9)
    @16 u32 unknown = 0                (NEW in v11 vs v9)
    @20 u32 entryCount
    @24 entries[entryCount] * 20 bytes (EntrySerializerV9 layout)
    then subfat tail: u32 count0, u32 count1, subfats...   (ignored for reads)

  Entry (20 bytes = 5 x u32 LE). v11 layout (FCBConverter GetFatEntriesDeserialize,
  "thx to miru") is DIFFERENT from v9 -- offset is 16-byte-aligned and split across
  two fields, CompressedSize is only 29 bits:
    a = NameHash high 32           <- NOTE: hash halves are stored HIGH word first
    b = NameHash low 32
    c = (UncompressedSize << 2) | CompressionScheme(2)
    dd = dwUnresolvedOffset
    e  = dwCompressedSize
    -> scheme = c & 3
       unc    = c >> 2
       offset = ((e >> 29) | (dd << 3)) << 4        (16-byte aligned)
       comp   = e & 0x1FFFFFFF                       (29 bits)

  CompressionScheme (FatEntry.cs enum): 0 = None(stored), 1 = LZO1x, 2 = LZ4.
  For FAT v11 (FC6) the LZ4 path is ONE standard LZ4 block over the whole entry
  (LZ4Codec.Decode(whole, whole)); the custom "Different" LZ4 is only for v9.

Entries are SORTED ascending by NameHash (binary search / monotonic).
"""
import struct, os, sys

MAGIC = 0x46415432


class Entry:
    __slots__ = ("hash", "unc", "scheme", "off", "comp", "pos")

    def __init__(self, hash, unc, scheme, off, comp, pos):
        self.hash = hash; self.unc = unc; self.scheme = scheme
        self.off = off; self.comp = comp; self.pos = pos   # pos = byte offset of this entry inside the .fat

    def __repr__(self):
        return f"Entry({self.hash:016x} sch={self.scheme} off={self.off} comp={self.comp} unc={self.unc})"


class Fat:
    """Reads a <name>.fat and gives access to its sibling <name>.dat."""

    def __init__(self, fat_path):
        self.fat_path = fat_path
        self.dat_path = fat_path[:-4] + ".dat" if fat_path.lower().endswith(".fat") else fat_path + ".dat"
        d = open(fat_path, "rb").read()
        self.raw = d
        magic, ver, plat = struct.unpack_from("<III", d, 0)
        if magic != MAGIC:
            raise ValueError(f"bad magic {magic:08x} in {fat_path}")
        self.version = ver
        self.platform = plat & 0xFF
        # header layout: v11 inserts two u32 (@12,@16) before the count@20.
        # Validate: count@20 with entries@24 must fit exactly.
        cnt20 = struct.unpack_from("<I", d, 20)[0]
        cnt12 = struct.unpack_from("<I", d, 12)[0]
        if ver >= 10 and 24 + cnt20 * 20 <= len(d):
            self.count = cnt20; start = 24
        else:                                   # v9-style header (count@12, entries@16)
            self.count = cnt12; start = 16
        self.entries = []
        by_hash = {}
        p = start
        for i in range(self.count):
            a, b, c, dd, e = struct.unpack_from("<IIIII", d, p)
            h = (a << 32) | b
            unc = c >> 2
            sch = c & 3
            if ver >= 11:
                off = ((e >> 29) | (dd << 3)) << 4      # v11: 16-byte aligned
                comp = e & 0x1FFFFFFF                    # v11: 29-bit compressed size
            elif ver == 10:
                off = (e >> 29) | (dd << 3)
                comp = e & 0x1FFFFFFF
            else:                                        # v9
                off = (dd << 2) | ((e >> 30) & 3)
                comp = e & 0x3FFFFFFF
            en = Entry(h, unc, sch, off, comp, p)
            self.entries.append(en)
            by_hash[h] = en
            p += 20
        self.by_hash = by_hash
        self.entries_end = p

    def read_raw(self, en):
        """Return the on-disk (possibly compressed) bytes for an entry."""
        with open(self.dat_path, "rb") as f:
            f.seek(en.off)
            return f.read(en.comp)

    def read_data(self, en):
        """Return the decompressed payload (scheme 0 stored, 1 LZO1x, 2 LZ4)."""
        raw = self.read_raw(en)
        if en.scheme == 0:
            return raw
        if en.scheme == 2:                 # v11 LZ4 = one standard block over the whole entry
            import lz4.block
            return lz4.block.decompress(raw, uncompressed_size=en.unc)
        if en.scheme == 1:
            from fc6_lzo import lzo_decompress
            return lzo_decompress(raw, en.unc)
        raise NotImplementedError(f"scheme {en.scheme}")


def _summary(path):
    f = Fat(path)
    sch = {}
    for e in f.entries:
        sch[e.scheme] = sch.get(e.scheme, 0) + 1
    print(f"{os.path.basename(path)}: ver={f.version} plat={f.platform} entries={f.count} "
          f"schemes={sch} entries_end={f.entries_end} fat_size={len(f.raw)} "
          f"dat={'exists' if os.path.exists(f.dat_path) else 'MISSING'}")
    return f


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for p in sys.argv[1:]:
        _summary(p)
