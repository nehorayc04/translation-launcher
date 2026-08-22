"""
Battlefield 6 (Frostbite) chunk reader — the SECOND content-addressing mechanism
alongside bundles (see bf6_toc.py). A "chunk" is a whole standalone resource
(texture, audio bank, or potentially a whole localization table) referenced by GUID
rather than packed into a bundle. Ported from `BF6Plugin.BF6TOCFile.ReadChunkData` /
`FindCatalogCasPatch` (the same BF6-specific override class that solved bf6_toc.py's
CASBundle mystery — see that module's docstring for how it was found).

Layout (all BIG-ENDIAN):
  1. ChunkFlags: `ChunkCount` x int32 at `556 + MetaData.chunk_flag_offset_position`
     (not used for resolution below, just read to advance/validate).
  2. Chunk GUID table at `556 + MetaData.chunk_guid_offset`, `ChunkCount` records of
     `{guid:16B (byte-reversed), num:u32}`. `num & 0xFFFFFF` is `listIndex*3` for the
     chunk's position (listIndex = 0..ChunkCount-1, ascending) -- used as the dict key
     matched against the entries below.
  3. Chunk entries at `556 + MetaData.chunk_entry_offset`, `ChunkCount` records, each:
     `FindCatalogCasPatch` = `{isInPatch:int16 BE (bool), catalogPersistentIndex:int32 BE,
     cas:int16 BE (truncated to byte)}` (8 bytes -- IDENTICAL shape to a flagged
     CASBundle entry's prefix) + `dataOffset:u32 BE` + `size:u32 BE` = 16 bytes/entry.
"""
from __future__ import annotations

import struct
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bf6_toc import TocFile  # noqa: E402


@dataclass
class ChunkEntry:
    guid: uuid.UUID
    list_index: int
    is_in_patch: bool
    catalog_persistent_index: int
    cas: int
    data_offset: int
    size: int


def read_chunks(t: TocFile) -> list[ChunkEntry]:
    data = t.data
    m = t.meta
    count = m.chunk_count
    if count == 0:
        return []

    def i32(o: int) -> int:
        return struct.unpack_from(">i", data, o)[0]

    def u32(o: int) -> int:
        return struct.unpack_from(">I", data, o)[0]

    # 1. chunk flags (skip content, just for completeness/offset validation)
    flags_pos = 556 + m.chunk_flag_offset_position
    _flags = [i32(flags_pos + 4 * i) for i in range(count)]

    # 2. GUID table -> list_index (ascending 0..count-1, matching num&0xFFFFFF == idx*3)
    guid_pos = 556 + m.chunk_guid_offset
    guids: list[tuple[uuid.UUID, int]] = []
    p = guid_pos
    for _ in range(count):
        raw = data[p:p + 16]
        # ReadGuidReverse: .NET Guid byte layout with the first 3 fields byte-reversed
        g = uuid.UUID(bytes=bytes(raw[3::-1]) + bytes(raw[5:3:-1]) + bytes(raw[7:5:-1]) + raw[8:16])
        num = u32(p + 16)
        guids.append((g, num & 0xFFFFFF))
        p += 20

    expected_pos = guid_pos + 20 * count
    if p != expected_pos:
        raise ValueError(f"chunk GUID table misaligned: at {p}, expected {expected_pos}")

    # 3. entries
    entries: list[ChunkEntry] = []
    p = 556 + m.chunk_entry_offset
    for k in range(count):
        guid, list_key = guids[k]
        is_in_patch = struct.unpack_from(">h", data, p)[0] != 0
        catalog_pidx = struct.unpack_from(">i", data, p + 2)[0]
        cas = struct.unpack_from(">h", data, p + 6)[0] & 0xFF
        data_offset = u32(p + 8)
        size = u32(p + 12)
        p += 16
        entries.append(ChunkEntry(guid, list_key, is_in_patch, catalog_pidx, cas, data_offset, size))
    return entries


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: bf6_chunk.py <file.toc> [max_print]")
        return 1
    t = TocFile.read(argv[0])
    limit = int(argv[1]) if len(argv) > 1 else 10
    print(t.summary())
    try:
        entries = read_chunks(t)
    except Exception as e:  # noqa: BLE001 - CLI diagnostic tool
        print(f"FAILED: {e}")
        return 1
    print(f"{len(entries)} chunks decoded OK")
    for e in entries[:limit]:
        print(f"  guid={e.guid} pidx={e.catalog_persistent_index} cas={e.cas} "
              f"offset={e.data_offset} size={e.size} patch={e.is_in_patch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
