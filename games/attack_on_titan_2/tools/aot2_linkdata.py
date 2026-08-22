"""
Attack on Titan 2 (Koei Tecmo, 2018) — LINKDATA_*.BIN container codec.

Format cracked via reuse of two public tools (per check-public-format-first /
engine-family-reuse-check-magic doctrine):
  - the-real-thunderlol/AOT2-MODDING-TOOLKIT (linkdata_extract.py) — AoT2-specific
    field layout, confirmed empirically against the real game files.
  - neptuwunium/Cethleann (Cethleann.Archive/LINKDATA.cs) — the authoritative C#
    LINKDATA reader from the wider Koei Tecmo "KTGL" engine-family toolkit; used
    to cross-validate field names/semantics and the DataTable/StringTable layout
    (Cethleann/Tables/{DataTable,StringTable}.cs, Cethleann/Extensions.cs).

Container layout (all little-endian):
    header:  u32 magic(0x00077DF9)  u32 entry_count  u32 offset_multiplier  u32 pad
    entry[N]: u32 offset_sectors  u32 pad  u32 compressed_size  u32 decompressed_size
        byte_offset = offset_sectors * offset_multiplier   (multiplier is PER FILE,
        empirically 256 for every AoT2 archive — NOT the 2048 used by the older
        "Attack on Titan / Wings of Freedom" TitanUnpacker tool for the same magic)
        decompressed_size == 0  =>  entry is stored RAW (csize bytes, no codec)
        decompressed_size != 0  =>  entry is zlib-compressed, in one or more
            fixed-32768-byte-decompressed BLOCKS (discovered 2026-08-10 —
            a single zlib.decompress(raw[8:]) SILENTLY TRUNCATES any entry
            whose dsize > 32768: Python's zlib.decompress() stops at the end
            of the first embedded deflate stream and drops the rest with NO
            error, so this looked correct for years on every small entry):
            raw[0:4]  = u32 decompressed_size (== dsize, redundant w/ the TOC)
            raw[4:8]  = u32 compressed length of the FIRST block's zlib stream
                        (needed to find where block 2 starts; the equivalent
                        4-byte field before every LATER block was empirically
                        NOT its compressed length — decoding doesn't need to
                        interpret it, only skip it, since zlib.decompressobj's
                        own end-of-stream detection finds each block's real
                        boundary via `.unused_data`)
            raw[8:]   = block 1's zlib stream (no leading size field)
            then, repeated until decompressed_size bytes are produced:
                u32 <block-N informational field, skip it>
                <block-N's own zlib stream>
            Every full block decompresses to exactly 32768 bytes; the final
            block is the dsize % 32768 remainder. See decompress_blocks().

Inside many entries sits a second, generic, engine-wide layout — the "DataTable"
(Cethleann calls it that; this is the same container used for the "battle text" /
story-dialogue string tables AND for arbitrary non-text blob bundles):
    u32 count
    count x { u32 offset, u32 size }      -- offset is absolute from the TABLE START,
                                              size is the string's UTF-8 byte length
                                              INCLUDING its NUL terminator
    <blob region>                          -- strings packed back-to-back, no padding,
                                              each NUL-terminated

`is_datatable()` is Cethleann's own heuristic (Extensions.cs `IsDataTable`): the
first record's declared offset must equal `4 + count*8` (unaligned) or that value
16-byte-aligned. Both forms are seen in AoT2; every table found so far in this game
uses the UNALIGNED form, and `encode_datatable()` reproduces that (round-trips
byte-identical on re-encode with no changes — verified against real archives).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

MAGIC = 0x00077DF9

BLOCK_SIZE = 32768  # 0x8000 — every full compressed block decodes to exactly this


def decompress_blocks(body: bytes, dsize: int) -> bytes:
    """Decode the block-compressed payload that follows an entry's 8-byte
    header (i.e. the caller has already sliced off raw[:8]). Handles both the
    common single-block case and the multi-block case transparently — see the
    module docstring for the format. Raises if it can't reach exactly `dsize`
    bytes (never silently returns a truncated buffer)."""
    out = bytearray()
    pos = 0
    first = True
    while len(out) < dsize:
        if not first:
            pos += 4  # skip the per-block informational size field
        first = False
        d = zlib.decompressobj()
        chunk = d.decompress(body[pos:])
        consumed = len(body[pos:]) - len(d.unused_data)
        if consumed == 0:
            raise ValueError(
                f"decompress_blocks: stuck at body offset {pos}, "
                f"produced {len(out)}/{dsize} bytes"
            )
        out += chunk
        pos += consumed
    if len(out) != dsize:
        raise ValueError(f"decompress_blocks: got {len(out)} bytes, expected {dsize}")
    return bytes(out)


class LinkData:
    """Read-only view of one LINKDATA_*.BIN container (loads the whole file into
    memory — the game's own archives run from a few KB up to ~7 GB; callers that
    only need the TOC + a handful of entries should prefer the streaming helpers
    in aot2_deploy.py for the very large A/B/C archives)."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        code, files, mult, pad = struct.unpack_from("<IIII", self.data, 0)
        if code != MAGIC:
            raise ValueError(f"{path}: bad LINKDATA magic 0x{code:08x}")
        self.files = files
        self.mult = mult
        self.pad = pad
        self.entries: list[tuple[int, int, int, int]] = []
        off = 16
        for _ in range(files):
            eo, epad, csize, dsize = struct.unpack_from("<IIII", self.data, off)
            self.entries.append((eo, epad, csize, dsize))
            off += 16

    def raw(self, i: int) -> bytes:
        eo, _epad, csize, _dsize = self.entries[i]
        start = eo * self.mult
        return self.data[start : start + csize]

    def read(self, i: int) -> bytes:
        eo, _epad, csize, dsize = self.entries[i]
        raw = self.raw(i)
        if dsize == 0:
            return raw
        # raw[0:4] = decompressed size (== dsize), raw[4:8] = block-1's
        # compressed length; the block-compressed stream starts at byte 8
        # (see decompress_blocks() — this can span MULTIPLE 32768-byte blocks).
        return decompress_blocks(raw[8:], dsize)


def is_datatable(buf: bytes) -> bool:
    if len(buf) < 8:
        return False
    count = struct.unpack_from("<I", buf, 0)[0]
    if count == 0 or count > 2_000_000:
        return False
    if 4 + count * 8 > len(buf):
        return False
    first_off = struct.unpack_from("<I", buf, 4)[0]
    est = 4 + count * 8
    est_aligned = (est + 15) & ~15
    return first_off == est or first_off == est_aligned


def parse_datatable(buf: bytes) -> list[bytes | None]:
    count = struct.unpack_from("<I", buf, 0)[0]
    out: list[bytes | None] = []
    for i in range(count):
        off, size = struct.unpack_from("<II", buf, 4 + i * 8)
        if off > len(buf):
            out.append(None)
            continue
        maxsize = min(size, len(buf) - off)
        out.append(buf[off : off + maxsize])
    return out


def read_cstring(b: bytes) -> str:
    idx = b.find(b"\x00")
    raw = b if idx == -1 else b[:idx]
    for enc in ("utf-8", "cp932", "latin1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return repr(raw)


def is_group_table(buf: bytes) -> bool:
    """A 'group table' (found 2026-08-10): u32 count + count*u32 BYTE OFFSETS
    into the SAME buffer, each pointing at an independent nested DataTable —
    used for big entries that bundle several unrelated string tables together
    (e.g. entry 0 in the REGION archives: an online-lobby dropdown, a general
    UI/settings string bank, the Manual table of contents, all as separate
    nested tables inside one archive entry)."""
    if is_datatable(buf):
        return False
    if len(buf) < 4:
        return False
    (count,) = struct.unpack_from("<I", buf, 0)
    if count == 0 or count > 100_000 or 4 + count * 4 > len(buf):
        return False
    offsets = struct.unpack_from(f"<{count}I", buf, 4)
    return all(0 <= o < len(buf) for o in offsets)


def parse_group_table(buf: bytes) -> list[list[str | None] | None]:
    """Returns one entry per nested group: a list of decoded strings if that
    group is itself a flat DataTable, else None (a group whose content isn't
    recognized — left untouched by encode_group_table)."""
    (count,) = struct.unpack_from("<I", buf, 0)
    offsets = struct.unpack_from(f"<{count}I", buf, 4)
    out: list[list[str | None] | None] = []
    for off in offsets:
        sub = buf[off:]
        if is_datatable(sub):
            blobs = parse_datatable(sub)
            out.append([read_cstring(b) if b is not None else None for b in blobs])
        else:
            out.append(None)
    return out


def encode_group_table(buf: bytes, groups: list[list[str] | None]) -> bytes:
    """Rebuilds a group table from a (possibly edited) per-group string list.
    Groups whose entry is None are copied VERBATIM from the original buffer
    (their raw bytes from their own offset to the next group's offset, or EOF
    for the last one) — used for any nested content that isn't a flat
    DataTable, so it's never touched even indirectly. Every DataTable group is
    RE-ENCODED via encode_datatable(), which round-trips byte-identical for an
    unmodified string list — so an unedited group reproduces exactly, and an
    edited one reflects the new content, with no assumption about the
    original layout beyond each group's own self-described length.

    Every group offset is 16-byte aligned (verified: `offset % 16 == 0` for
    all groups across both REGION_EU and REGION_EDEN_EU entry 0), with the
    gap after each group's encoded bytes zero-padded up to that boundary
    (verified against the real padding bytes) — reproduced here so a
    group-table edit round-trips EXACTLY when no group's content changed."""
    (count,) = struct.unpack_from("<I", buf, 0)
    offsets = list(struct.unpack_from(f"<{count}I", buf, 4))
    assert len(groups) == count
    out = bytearray()
    out += struct.pack("<I", count)
    out += b"\x00" * (count * 4)  # offset slots, patched below
    new_offsets = []
    for gi, (off, g) in enumerate(zip(offsets, groups)):
        if len(out) % 16:
            out += b"\x00" * (16 - len(out) % 16)
        new_offsets.append(len(out))
        if g is None:
            end = offsets[gi + 1] if gi + 1 < count else len(buf)
            out += buf[off:end].rstrip(b"\x00") if gi + 1 < count else buf[off:end]
        else:
            out += encode_datatable(g)
    for gi, o in enumerate(new_offsets):
        struct.pack_into("<I", out, 4 + gi * 4, o)
    if len(out) % 16:
        out += b"\x00" * (16 - len(out) % 16)
    return bytes(out)


def encode_datatable(strings: list[str]) -> bytes:
    """Inverse of parse_datatable()+read_cstring() — rebuilds the flat offset/size
    header + NUL-terminated UTF-8 blob region, unaligned layout (matches the game's
    own convention on every table sampled). Verified: encode_datatable(decode(x))
    round-trips BYTE-IDENTICAL for an unmodified string list."""
    count = len(strings)
    header_size = 4 + count * 8
    encoded = [s.encode("utf-8") + b"\x00" for s in strings]
    sizes = [len(e) for e in encoded]
    offsets = []
    cur = header_size
    for sz in sizes:
        offsets.append(cur)
        cur += sz
    out = bytearray()
    out += struct.pack("<I", count)
    for off, sz in zip(offsets, sizes):
        out += struct.pack("<II", off, sz)
    for e in encoded:
        out += e
    return bytes(out)
