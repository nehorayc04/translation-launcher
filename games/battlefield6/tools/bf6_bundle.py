"""
Battlefield 6 (Frostbite) SuperBundle-content reader — parses the metadata blob at a
bundle's entry[0] (per bf6_toc.py's CASBundle chain) into its ebx/res/chunk lists,
matching each list entry to its actual data range in entries[1:].

Ported from `FMT.Core.{SBHeaderInformation,BundleReader}` (decompiled from the same
FMT.Core assembly that gave us CompressedStringHandler/CASDataReader — see bf6_toc.py's
docstring for the carving method) and `FMT.FileTools.ResourceType` (found as a real
enum with explicit uint32 "hash-shaped" values, in a newly-carved small assembly whose
raw bytes literally spell out every resource-type name as one flat NUL-separated blob —
that's how `LocalizedStringResource = 1585851909u` was found).

KEY DISCOVERY (validated against real bytes: bundle 185/ui.toc, the byte math for
metaOffset matched the computed cumulative size EXACTLY): the inner SuperBundle format
uses a MIXED endianness, different from the outer .toc container:
  - `size` (SBHeaderInformation's own first field) is BIG-endian (matches the outer
    container's convention).
  - EVERYTHING ELSE inside the SuperBundle (totalCount, ebxCount, resCount, chunkCount,
    stringOffset, metaOffset, metaSize, and every per-entry field in the ebx/res/chunk
    lists) is LITTLE-endian -- i.e. the *inner* bundle data is written in the shipping
    platform's native byte order (Win32 = x86 = little-endian), while the *outer*
    container/catalog system is platform-normalized big-endian. This was NOT obvious
    from the decompiled C# alone (the `Endian` enum's numeric tags don't map onto a
    single global rule) and was only confirmed by testing candidate byte orders against
    real data until the structural math (metaOffset == the actual cumulative byte
    length of everything before it) checked out exactly.

Layout of the metadata blob (entry[0] of a bundle's CASBundle.Entries):
    size:i32 BE, magic:4B (0xD68E799D), totalCount/ebxCount/resCount/chunkCount:i32 LE,
    stringOffset/metaOffset/metaSize:i32 LE (each +4 after reading, per the decompile)
  then totalCount x 20-byte SHA1 hashes
  then ebxCount x {nameOffset:u32 LE, originalSize:u32 LE}   (name = null-term string at
       header_start + stringOffset + nameOffset)
  then resCount x {nameOffset:u32 LE, originalSize:u32 LE}         -- pass 1 (names)
  then resCount x {resType:u32 LE}                                  -- pass 2
  then resCount x {resMeta:16 raw bytes}                            -- pass 3
  then resCount x {resRid:u64 LE}                                   -- pass 4
  then chunkCount x {guid:16B, logicalOffset:u32 LE, originalSize:u32 LE}

The i-th ebx/res/chunk entry's ACTUAL DATA lives at `CasBundleEntry` index
`1 + i` (ebx first, then res, then chunks, in that order) of the SAME bundle's
resolved entries list (bf6_toc.py:read_cas_bundle) -- entry[0] is always this metadata
blob itself.
"""
from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

MAGIC = bytes.fromhex("d68e799d")

# FMT.FileTools.ResourceType (partial -- the one we care about; add more as needed)
RESTYPE_LOCALIZED_STRING = 1585851909


@dataclass
class SBEntry:
    kind: str  # "ebx" | "res" | "chunk"
    name: str | None
    original_size: int
    res_type: int | None = None
    data_index: int = 0  # index into the bundle's CasBundleEntry list (data lives here)


@dataclass
class SBInfo:
    size: int
    total_count: int
    ebx_count: int
    res_count: int
    chunk_count: int
    entries: list[SBEntry] = field(default_factory=list)


def parse_bundle_meta(data: bytes) -> SBInfo:
    """`data` = the raw bytes of a bundle's metadata blob (CasBundleEntry index 0)."""
    if data[4:8] != MAGIC:
        raise ValueError(f"bad SBHeaderInformation magic: {data[4:8].hex()} (expected {MAGIC.hex()})")

    def be32(o: int) -> int:
        return struct.unpack_from(">i", data, o)[0]

    def le32(o: int) -> int:
        return struct.unpack_from("<i", data, o)[0]

    def leu32(o: int) -> int:
        return struct.unpack_from("<I", data, o)[0]

    header_start = 0
    size = be32(0)
    total_count = le32(8)
    ebx_count = le32(12)
    res_count = le32(16)
    chunk_count = le32(20)
    string_offset = le32(24) + 4

    p = 36
    # totalCount x 20-byte SHA1 (skip content)
    p += 20 * total_count

    def read_name(name_off: int) -> str:
        pos = header_start + string_offset + name_off
        end = data.index(b"\x00", pos)
        return data[pos:end].decode("utf-8", errors="replace")

    entries: list[SBEntry] = []
    data_idx = 1  # entry[0] is this metadata blob itself

    for _ in range(ebx_count):
        name_off = leu32(p)
        orig_size = leu32(p + 4)
        p += 8
        entries.append(SBEntry("ebx", read_name(name_off), orig_size, data_index=data_idx))
        data_idx += 1

    res_name_offsets = []
    res_sizes = []
    for _ in range(res_count):
        name_off = leu32(p)
        orig_size = leu32(p + 4)
        p += 8
        res_name_offsets.append(name_off)
        res_sizes.append(orig_size)

    res_types = []
    for _ in range(res_count):
        res_types.append(leu32(p))
        p += 4
    p += 16 * res_count  # resMeta, skip
    p += 8 * res_count  # resRid, skip

    for i in range(res_count):
        entries.append(SBEntry("res", read_name(res_name_offsets[i]), res_sizes[i], res_types[i], data_idx))
        data_idx += 1

    for _ in range(chunk_count):
        # guid(16) + logicalOffset(4) + originalSize(4) = 24 bytes; skip content, just count
        p += 24
        entries.append(SBEntry("chunk", None, 0, data_index=data_idx))
        data_idx += 1

    return SBInfo(size, total_count, ebx_count, res_count, chunk_count, entries)


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: bf6_bundle.py <win32_root> <layout.toc> <file.toc> <bundle_index_or_name_substr>")
        return 1
    from bf6_toc import TocFile, read_cas_bundle
    from bf6_catalog import build_catalog_list, build_persistent_index_map, resolve_cas_path

    win32_root, layout_toc, toc_path, sel = argv[:4]
    catalogs = build_catalog_list(layout_toc)
    pidx_map = build_persistent_index_map(catalogs)
    t = TocFile.read(toc_path)

    if sel.isdigit():
        targets = [t.bundles[int(sel)]]
    else:
        needle = sel.lower()
        targets = [b for b in t.bundles if b.name and needle in b.name.lower()]

    for b in targets:
        entries = read_cas_bundle(t.data, b.offset)
        if not entries:
            continue
        e0 = entries[0]
        ordv = pidx_map.get(e0.catalog_persistent_index)
        cat = catalogs[ordv] if ordv is not None else None
        if not cat:
            continue
        path = resolve_cas_path(win32_root, cat, e0.cas, e0.is_in_patch)
        if not path.exists():
            continue
        with open(path, "rb") as f:
            f.seek(e0.bundle_offset)
            meta_bytes = f.read(e0.bundle_size)
        try:
            info = parse_bundle_meta(meta_bytes)
        except Exception as e:  # noqa: BLE001
            print(f"bundle[{b.index}] {b.name!r}: parse FAILED: {e}")
            continue
        print(f"bundle[{b.index}] {b.name!r} ebx={info.ebx_count} res={info.res_count} chunk={info.chunk_count}")
        for e in info.entries:
            if e.data_index < len(entries):
                de = entries[e.data_index]
                print(f"  [{e.kind}] name={e.name!r} resType={e.res_type} "
                      f"data@entries[{e.data_index}] cas={de.cas} off={de.bundle_offset} size={de.bundle_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
