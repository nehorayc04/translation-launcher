"""
Battlefield 6 (Frostbite) .toc reader — read-only, pure Python, no external deps.

Format reverse-engineered by decompiling the public community tool "FMT" (Frostbite
Modding Tool, FMTDev/FMT.Releases release FMT-26.10.9654.14105, 2026-06-07 — the first
release with an "EARLY WIP" BF6Profile.json + BF6Plugin.dll). FMT is a large .NET
single-file bundle; BF6Plugin.dll/BF6SDK.dll are normal small managed DLLs and were
decompiled directly with ilspycmd. The core FMT.Core.TOCFile / FMT.FileTools classes
live embedded inside the big bundle and were extracted by carving out individual
embedded PE assemblies (each still has its own MZ/PE header, found by scanning for
valid `e_lfanew` -> "PE\\0\\0" pairs) and decompiling those.

KEY FINDING: the .toc container is NOT AES/XOR encrypted (BF6Profile.json has no
"RequiresKey"/"KeyFile"/"Deobfuscator" field, and FMT.Core.TOCFile.Read() never calls
any crypto/deobfuscate API). What looks like "high-entropy encrypted data" in a hex
dump is actually a fixed 256-byte cryptographic SIGNATURE ("ToCSig", almost certainly
RSA-2048, used by the game to detect tampering) plus a 292-byte reserved/build-stamp
field ("ToCXor") that FMT reads and discards unmodified. Real, fully-plain structured
data starts at a FIXED offset of 556 bytes. Validated against real local BF6 files:
characters.toc and globals.toc decode to small, monotonically-sane offsets/counts in
big-endian; en.toc/voen.toc decode to a legitimate empty (0 bundles / 0 chunks) stub.

Layout of a .toc file:
    [0:8]     ToCVersion   (b"\\x00\\xd1\\xce\\x01\\x00\\x00\\x00\\x00" observed)
    [8:264]   ToCSig       (256 B, opaque — tamper-detection signature, unused for read)
    [264:556] ToCXor       (292 B, opaque reserved/build region, unused for read)
    [556:]    MetaData     (12x int32 BE, +3 more if TocFlags has CompressedStrings)
    ... bundle references / bundle entries / chunk flags+guids+entries / compressed
        string table / CAS-bundle offset tables, all at MetaData-relative offsets ...

This module also implements bundle enumeration (ReadBundleData) + real bundle NAME
recovery. Bundle names are NOT stored as plain null-terminated strings in these files —
they're packed into a **custom binary Huffman tree** (`FMT.Core.CompressedStringHandler`):
a flattened binary-tree array (`CompressedStringTable`, pairs of child-node ints per
node; a negative value `v` at a leaf means the decoded character is `chr(-1 - v)`) plus
a packed bitstream (`CompressedStringNames`, read 1 bit at a time, LSB-first per 32-bit
word). Each bundle's `BundleNameOffset` is simply the STARTING BIT INDEX into that shared
bitstream. This is NOT a general compression codec (no Oodle/zlib/LZ4 needed here at
all) — it's a small, fully-portable bit-tree walk, ported below as `read_huffman_string`.

Per-chunk body parsing (`ReadChunkData`) and per-bundle CAS-offset tables
(`ReadCasBundles`) are documented in `RECON.md` and NOT yet ported here — those don't
carry a "name" (chunks are raw GUID-keyed blobs) and are lower priority than proving we
can already read real bundle names, which this module now does.
"""
from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from enum import IntFlag
from pathlib import Path

MAGIC = b"\x00\xd1\xce\x01"


class TocFlags(IntFlag):
    NONE = 0
    COMPRESSED_STRINGS = 4  # observed value on every non-empty real .toc so far


class BundleFlags(IntFlag):
    NONE = 0
    # top 2 bits of the packed `num` field in each bundle-table entry (mask 0xC0000000);
    # exact meaning of each bit not yet reverse-engineered — kept as a raw flag for now.
    BIT30 = 0x40000000
    BIT31 = 0x80000000


@dataclass
class BundleRef:
    index: int
    name_offset: int
    offset: int
    size: int
    flags: int
    reference: int
    name: str | None = None


@dataclass
class CasBundleEntry:
    is_in_patch: bool
    catalog_persistent_index: int | None  # raw on-disk value; None = inherited from a
                                           # previous flagged entry (see docstring)
    cas: int
    bundle_offset: int
    bundle_size: int


def read_cas_bundle(data: bytes, bundle_offset: int) -> list[CasBundleEntry]:
    """Port of `BF6Plugin.BF6TOCFile.ReadCasBundles` -- the BF6-SPECIFIC override of
    `FMT.Core.TOCFile.ReadCasBundles`, found in `notes/FMT_decompiled_BF6Plugin/
    BF6Plugin/BF6TOCFile.cs` (decompiled early in the project's first session, but not
    re-examined for this method until a later pass -- the generic FMT.Core version is
    NOT what BF6 actually uses, which is why an earlier attempt at this function, ported
    from the generic class, produced garbage against real bytes).

    `bundle_offset` is a `BundleRef.offset` value; the sub-header sits at
    `556 + bundle_offset`, all integers BIG-ENDIAN throughout (like everything else in
    this container).

    Layout: **9x int32 BE** (unk1, unk2, FlagsOffset, EntriesCount, EntriesOffset,
    HeaderSize[always 36 for BF6 -- 9*4=36, confirming the field count], unk4, unk5,
    unk6) -- one MORE field than the generic FMT.Core version's 8, which is exactly why
    HeaderSize reads as 36 and not the generic class's expected 32. Then `EntriesCount`
    flag bytes at `+FlagsOffset`, then `EntriesCount` records at `+EntriesOffset`:

    - If `Flags[j] == 128` (NOT `== 1` -- this is the other key difference from the
      generic class, and the reason the generic port's `flags[j]==1` check failed):
      read `isInPatch:int16 BE (as bool)`, `catalogPersistentIndex:int32 BE`,
      `cas:int16 BE (truncated to a byte)` -- an 8-byte prefix, NOT the generic
      class's 4-byte one. `catalogPersistentIndex` is looked up via
      `IFileSystemService.CatalogsIndexed[persistentIndex]` at runtime -- i.e. it's
      the catalog's `persistentIndex` field from `layout.toc`, NOT the small ordinal
      `bf6_catalog.py` otherwise uses. Use `bf6_catalog.build_persistent_index_map()`
      to convert it to an ordinal `CatalogEntry`.
    - Otherwise (`Flags[j] != 128`): no prefix at all -- just the offset+size pair,
      INHERITING the catalog/cas/patch values from the most recent flagged entry
      (entry 0 is always flagged in every real bundle observed so far).
    - Then, always: `offset:u32 BE`, `size:u32 BE` -- a byte range into that catalog's
      `cas_NN.cas` file.

    **VALIDATED against real bytes**: resolved entries form long, perfectly contiguous
    chains (`offset[n+1] == offset[n] + size[n]`) and the resolved catalog/cas/offset
    genuinely decode to a real `RIFF....EBX/EBXD` resource in the real `cas_NN.cas` file
    with a readable embedded asset path (e.g. the `fontconfiguration_languageformat_
    arabicsa` bundle's entry resolves to literal ASCII
    `Common/UI/Assets/Fonts/FontBFText/BFText-Regular-AR`). See RECON.md for the full
    validation writeup.
    """
    pos = 556 + bundle_offset
    header_start = pos

    def i32(o: int) -> int:
        return struct.unpack_from(">i", data, o)[0]

    flags_offset = i32(pos + 8)
    entries_count = i32(pos + 12)
    entries_offset = i32(pos + 16)
    header_size = i32(pos + 20)
    if header_size != 36:
        raise ValueError(f"BF6 CASBundle HeaderSize should be 36, got {header_size}")

    flags_pos = header_start + flags_offset
    flags = data[flags_pos:flags_pos + entries_count]

    entries: list[CasBundleEntry] = []
    p = header_start + entries_offset
    is_in_patch = False
    cas = 0
    catalog_pidx: int | None = None
    for j in range(entries_count):
        if flags[j] == 128:
            is_in_patch = struct.unpack_from(">h", data, p)[0] != 0
            catalog_pidx = struct.unpack_from(">i", data, p + 2)[0]
            cas = struct.unpack_from(">h", data, p + 6)[0] & 0xFF
            p += 8
        offset = struct.unpack_from(">I", data, p)[0]
        size = struct.unpack_from(">I", data, p + 4)[0]
        p += 8
        entries.append(CasBundleEntry(is_in_patch, catalog_pidx, cas, offset, size))
    return entries


def read_huffman_string(table: list[int], data: list[int], bit_index: int) -> str:
    """Port of FMT.Core.CompressedStringHandler.ReadCompressedString.

    `table` = the flattened binary tree (pairs of child ints per node; a negative
    value v is a leaf meaning character chr(-1 - v), 0x00 terminates the string).
    `data`  = the packed bitstream (each element is one 32-bit word; bits are
    consumed LSB-first: bit (bit_index % 32) of word (bit_index // 32)).
    """
    out: list[str] = []
    while True:
        node = len(table) // 2 - 1  # root
        while True:
            bit = (data[bit_index // 32] >> (bit_index % 32)) & 1
            node = table[node * 2 + bit]
            bit_index += 1
            if node < 0:
                break
        c = chr((-1 - node) & 0xFFFF)
        if c == "\0":
            break
        out.append(c)
    return "".join(out)


@dataclass
class ContainerMetaData:
    bundle_reference_offset: int = 0
    bundle_offset: int = 0
    bundle_count: int = 0
    chunk_flag_offset_position: int = 0
    chunk_guid_offset: int = 0
    chunk_count: int = 0
    chunk_entry_offset: int = 0
    unk1_offset: int = 0
    name_offset: int = 0
    data_offset: int = 0
    unk9_count: int = 0
    toc_flags: TocFlags = TocFlags.NONE
    compressed_string_count: int = 0
    compressed_string_table_count: int = 0
    compressed_string_offset: int = 0


@dataclass
class TocFile:
    path: Path
    toc_version: bytes = b""
    toc_sig: bytes = b""
    toc_xor: bytes = b""
    meta: ContainerMetaData = field(default_factory=ContainerMetaData)
    header_size: int = 556
    bundles: list[BundleRef] = field(default_factory=list)
    data: bytes = b""

    @classmethod
    def read(cls, path: str | Path) -> "TocFile":
        path = Path(path)
        data = path.read_bytes()
        if data[:4] != MAGIC:
            raise ValueError(f"{path}: bad magic {data[:4].hex()} (expected {MAGIC.hex()})")

        self = cls(path=path)
        self.data = data
        self.toc_version = data[0:8]
        self.toc_sig = data[8:264]
        self.toc_xor = data[264:556]

        off = 556
        if len(data) < off + 48:
            # legitimate empty stub (e.g. en.toc/voen.toc in a partial install)
            return self

        def i32(o: int) -> int:
            return struct.unpack_from(">i", data, o)[0]

        m = self.meta
        m.bundle_reference_offset = i32(off); off += 4
        m.bundle_offset = i32(off); off += 4
        m.bundle_count = i32(off); off += 4
        m.chunk_flag_offset_position = i32(off); off += 4
        m.chunk_guid_offset = i32(off); off += 4
        m.chunk_count = i32(off); off += 4
        m.chunk_entry_offset = i32(off); off += 4
        m.unk1_offset = i32(off); off += 4
        m.name_offset = i32(off); off += 4
        m.data_offset = i32(off); off += 4
        m.unk9_count = i32(off); off += 4
        m.toc_flags = TocFlags(i32(off)); off += 4
        if TocFlags.COMPRESSED_STRINGS in m.toc_flags and len(data) >= off + 12:
            m.compressed_string_count = i32(off); off += 4
            m.compressed_string_table_count = i32(off); off += 4
            m.compressed_string_offset = i32(off); off += 4

        self.header_size = off

        if m.bundle_count:
            self._read_bundle_table(data)
        if m.bundle_count and TocFlags.COMPRESSED_STRINGS in m.toc_flags and m.compressed_string_count:
            self._read_bundle_names(data)

        return self

    def _read_bundle_table(self, data: bytes) -> None:
        m = self.meta

        def i32(o: int) -> int:
            return struct.unpack_from(">i", data, o)[0]

        def i64(o: int) -> int:
            return struct.unpack_from(">q", data, o)[0]

        # BundleReferences[] — not needed for name recovery, skip (kept for completeness)
        off = 556 + m.bundle_offset
        for i in range(m.bundle_count):
            name_offset = i32(off)
            num = i32(off + 4)
            offset = i64(off + 8)
            off += 16
            self.bundles.append(
                BundleRef(
                    index=i,
                    name_offset=name_offset,
                    offset=offset,
                    size=num & 0x3FFFFFFF,
                    flags=num & 0xC0000000,
                    reference=0,
                )
            )

    def _read_bundle_names(self, data: bytes) -> None:
        m = self.meta
        name_words = struct.unpack_from(f">{m.compressed_string_count}I", data, 556 + m.name_offset)
        table = list(struct.unpack_from(f">{m.compressed_string_table_count}i", data, 556 + m.compressed_string_offset))
        for b in self.bundles:
            try:
                b.name = read_huffman_string(table, name_words, b.name_offset)
            except Exception:  # noqa: BLE001 - diagnostic tool, keep going on a bad offset
                b.name = None

    def summary(self) -> str:
        m = self.meta
        return (
            f"{self.path.name}: version={self.toc_version.hex()} "
            f"bundles={m.bundle_count} chunks={m.chunk_count} flags={m.toc_flags!r} "
            f"bundleOffset={m.bundle_offset} chunkGuidOffset={m.chunk_guid_offset} "
            f"nameOffset={m.name_offset} dataOffset={m.data_offset}"
        )


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: bf6_toc.py <file.toc> [more.toc ...]")
        print("       bf6_toc.py --bundles <file.toc> [grep_substring]")
        return 1

    if argv[0] == "--bundles":
        rest = argv[1:]
        if not rest:
            print("usage: bf6_toc.py --bundles <file.toc> [grep_substring]")
            return 1
        toc_path = rest[0]
        needle = rest[1].lower() if len(rest) > 1 else None
        t = TocFile.read(toc_path)
        print(t.summary())
        shown = 0
        for b in t.bundles:
            name = b.name or "<undecoded>"
            if needle and needle not in name.lower():
                continue
            print(f"  [{b.index:5d}] offset={b.offset:>12d} size={b.size:>10d} flags=0x{b.flags:x}  {name}")
            shown += 1
        print(f"-- {shown}/{len(t.bundles)} bundles shown --")
        return 0

    for p in argv:
        try:
            t = TocFile.read(p)
        except Exception as e:  # noqa: BLE001 - CLI diagnostic tool
            print(f"{p}: ERROR {e}")
            continue
        print(t.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
