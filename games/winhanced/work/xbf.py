"""XBF v2 (compiled WinUI XAML) reader/writer -- string-table surgery.

Layout, derived from the real bytes (all little-endian):

    0x00  char[4]   magic 'XBF\0'
    0x04  u32       metadataSize   -- counted from 0x0c
    0x08  u32       nodeSize       -- the node stream that follows the metadata
    --- metadata base = 0x0c ; every offset below is RELATIVE to it ---
    0x0c  u32       majorVersion (2)
    0x10  u32       minorVersion (1)
    0x14  u64       stringTableOffset        (always 0x78 == this header's size)
    0x1c  u64       assemblyListOffset
    0x24  u64       typeNamespaceListOffset
    0x2c  u64       typeListOffset
    0x34  u64       propertyListOffset
    0x3c  u64       xmlNamespaceListOffset
    0x44  char[64]  hash (ASCII hex of the source XAML -- a build stamp)
    0x84  ...       string table

    file == 0x0c + metadataSize + nodeSize

String table:  u32 count, then count x [u32 charLen][UTF-16LE chars][u16 0x0000]
               (each entry is NUL-terminated -- the terminator is NOT counted
               in charLen, and omitting it desyncs the whole table)

The node stream refers to strings by INDEX, so translating is a pure
string-table rewrite: replace the text, shift the five later block offsets and
metadataSize by the byte delta. Nothing else moves.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = b"XBF\x00"
META_BASE = 0x0C
HASH_LEN = 64
_N_OFFSETS = 6
# major, minor, 6x u64 offset, hash
_HDR = f"<II{_N_OFFSETS}Q{HASH_LEN}s"
HDR_SIZE = struct.calcsize(_HDR)  # 0x78


@dataclass
class Xbf:
    path: Path
    raw: bytes
    node_size: int
    major: int
    minor: int
    offsets: list[int]
    hash: bytes
    strings: list[str] = field(default_factory=list)
    table_start: int = 0
    table_end: int = 0


def parse(path) -> Xbf:
    path = Path(path)
    raw = path.read_bytes()
    if raw[:4] != MAGIC:
        raise ValueError(f"{path.name}: not XBF (magic {raw[:4]!r})")

    meta_size, node_size = struct.unpack_from("<II", raw, 4)
    if META_BASE + meta_size + node_size != len(raw):
        raise ValueError(
            f"{path.name}: size mismatch "
            f"({META_BASE}+{meta_size}+{node_size} != {len(raw)})"
        )

    major, minor, *rest = struct.unpack_from(_HDR, raw, META_BASE)
    offsets = list(rest[:_N_OFFSETS])
    hsh = rest[_N_OFFSETS]
    if major != 2:
        raise ValueError(f"{path.name}: unsupported XBF major version {major}")
    if offsets[0] != HDR_SIZE:
        raise ValueError(f"{path.name}: string table not first (0x{offsets[0]:x})")

    start = META_BASE + offsets[0]
    end_limit = META_BASE + offsets[1]
    pos = start
    (count,) = struct.unpack_from("<I", raw, pos)
    pos += 4
    strings: list[str] = []
    for i in range(count):
        (n,) = struct.unpack_from("<I", raw, pos)
        pos += 4
        if pos + n * 2 + 2 > end_limit:
            raise ValueError(f"{path.name}: string {i} overruns table")
        strings.append(raw[pos : pos + n * 2].decode("utf-16le"))
        pos += n * 2
        term = raw[pos : pos + 2]
        if term != b"\x00\x00":
            raise ValueError(f"{path.name}: string {i} not NUL-terminated ({term!r})")
        pos += 2

    x = Xbf(path, raw, node_size, major, minor, offsets, hsh, strings)
    x.table_start = start
    x.table_end = pos
    return x


def code_string_indices(x: Xbf) -> set[int]:
    """Indices whose string is a CODE name, proven from the metadata tables.

    Layouts (verified against real files):
        assemblyList     u32 count, 8B/entry  -> [u32 ?][u32 strIdx]
        typeNamespaceList u32 count, 8B/entry -> [u32 ?][u32 strIdx]
        typeList         u32 count, 12B/entry -> [u32 ?][u32 nsIdx][u32 strIdx]
        propertyList     u32 count, 12B/entry -> [u32 ?][u32 typeIdx][u32 strIdx]
        xmlNamespaceList u32 count, 4B/entry  -> [u32 strIdx]
    Translating any of these renames a type/property/namespace -> instant break.
    """
    ends = [META_BASE + o for o in x.offsets[1:]]
    ends.append(META_BASE + (len(x.raw) - META_BASE - x.node_size))
    widths = {1: 8, 2: 8, 3: 12, 4: 12, 5: 4}
    out: set[int] = set()
    for i, w in widths.items():
        s, e = META_BASE + x.offsets[i], ends[i]
        if e - s < 4:
            continue
        (count,) = struct.unpack_from("<I", x.raw, s)
        pos = s + 4
        for _ in range(count):
            if pos + w > e:
                break
            idx = struct.unpack_from("<I", x.raw, pos + w - 4)[0]
            if 0 <= idx < len(x.strings):
                out.add(idx)
            pos += w
    return out


def _pack_table(strings: list[str]) -> bytes:
    out = [struct.pack("<I", len(strings))]
    for s in strings:
        b = s.encode("utf-16le")
        out.append(struct.pack("<I", len(b) // 2))
        out.append(b)
        out.append(b"\x00\x00")
    return b"".join(out)


def build(x: Xbf, new_strings: list[str]) -> bytes:
    if len(new_strings) != len(x.strings):
        raise ValueError("string count must not change")

    old_len = x.table_end - x.table_start
    new = _pack_table(new_strings)
    # keep any padding that sat between the table end and the next block
    pad = x.raw[x.table_end : META_BASE + x.offsets[1]]
    delta = len(new) - old_len

    offsets = list(x.offsets)
    for i in range(1, _N_OFFSETS):
        offsets[i] += delta

    meta_size = (len(x.raw) - META_BASE - x.node_size) + delta
    head = struct.pack("<4sII", MAGIC, meta_size, x.node_size)
    head += struct.pack(_HDR, x.major, x.minor, *offsets, x.hash)
    out = head + new + pad + x.raw[META_BASE + x.offsets[1] :]

    # invariant the loader itself checks
    assert META_BASE + meta_size + x.node_size == len(out), "size invariant broken"
    return out


def build_fixed_size(x: Xbf, new_strings: list[str]) -> bytes:
    """Rebuild keeping the payload's EXACT original byte length -- required when
    the XBF is embedded in a container (Winhanced.pri) that records its offset.

    The blob is built normally (offsets and metadataSize shifted correctly) and
    the slack is added AFTER the node stream. The loader takes the file's extent
    from `META_BASE + metadataSize + nodeSize`, so trailing bytes are never read,
    while the container sees an unchanged slot size.

    Do NOT instead pad between the string table and the next metadata block:
    that leaves every header offset untouched but inserts a gap the loader does
    not tolerate -- it hangs the app during XAML load, with no log and no crash.
    (Verified: an equal-length edit, which needs no padding at all, loads fine;
    the same edit made shorter and gap-padded does not.)
    """
    if len(new_strings) != len(x.strings):
        raise ValueError("string count must not change")

    blob = build(x, new_strings)
    if len(blob) > len(x.raw):
        raise ValueError(
            f"{x.path.name}: payload grew {len(blob) - len(x.raw)} bytes past its "
            "slot; delta-0 impossible"
        )
    out = blob + b"\x00" * (len(x.raw) - len(blob))
    assert len(out) == len(x.raw), "delta-0 violated"
    return out


def selftest(paths, verbose=False):
    ok = bad = 0
    total_strings = 0
    for p in paths:
        try:
            x = parse(p)
            rebuilt = build(x, list(x.strings))
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {Path(p).name}: {e}")
            bad += 1
            continue
        if rebuilt == x.raw:
            ok += 1
            total_strings += len(x.strings)
            if verbose:
                print(f"  ok {Path(p).name:<44} {len(x.strings):>5} strings")
        else:
            bad += 1
            print(f"  ROUNDTRIP-FAIL {Path(p).name}")
    return ok, bad, total_strings


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Program Files\Winhanced")
    files = sorted(root.rglob("*.xbf"))
    print(f"{len(files)} xbf files")
    ok, bad, n = selftest(files, verbose="-v" in sys.argv)
    print(f"identity round-trip: {ok} ok / {bad} bad   ({n} strings)")
