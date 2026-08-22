"""Hogwarts Legacy MAIN-<locale>.bin / SUB-<locale>.bin codec ("AVAFDICT 2.0").

Pure-Python port of insomnious/parseltongue's Program.cs (C#), verified against the
game's own shipped files. Format (little-endian):

    magic       32 bytes  UTF-16LE "AVAFDICT 2.0   \\0" (16 chars)
    entryCount  int64
    headerSize  int64     always 72
    entriesSize int64     entryCount * 24
    dataStart   int64     headerSize + entriesSize
    dataSize    int64     total bytes of the data section

    entryCount x 24-byte entry records:
        keyOffset   int64   (relative to dataStart)
        keySize     int32   (UTF-8 byte length)
        valueOffset int64   (relative to dataStart)
        valueSize   int32   (UTF-8 byte length)

    data section: for every entry in order, UTF-8 key bytes immediately
    followed by UTF-8 value bytes (no separator/terminator) — one flat blob,
    offsets are a running cumulative total across ALL entries.

No compression, no encryption, no padding tricks — a fresh write never needs to
match the original byte-for-byte (unlike the delta=0 games elsewhere in this repo).
"""
import struct

MAGIC = "AVAFDICT 2.0   \0"
HEADER_SIZE = 72


def decode(data: bytes) -> dict:
    magic = data[0:32].decode("utf-16-le")
    if magic != MAGIC:
        raise ValueError(f"bad magic: {magic!r}")
    entry_count, header_size, entries_size, data_start, data_size = struct.unpack_from(
        "<qqqqq", data, 32
    )
    assert header_size == HEADER_SIZE, header_size
    assert entries_size == entry_count * 24, (entries_size, entry_count)

    out = {}
    pos = HEADER_SIZE
    for _ in range(entry_count):
        key_off, key_size, val_off, val_size = struct.unpack_from("<qiqi", data, pos)
        pos += 24
        key = data[data_start + key_off : data_start + key_off + key_size].decode("utf-8")
        val = data[data_start + val_off : data_start + val_off + val_size].decode("utf-8")
        out[key] = val
    return out


def encode(entries: dict) -> bytes:
    entry_count = len(entries)
    entries_size = entry_count * 24
    data_start = HEADER_SIZE + entries_size

    headers = bytearray()
    blob = bytearray()
    offset = 0
    for key, val in entries.items():
        kb = key.encode("utf-8")
        vb = val.encode("utf-8")
        headers += struct.pack("<qiqi", offset, len(kb), offset + len(kb), len(vb))
        offset += len(kb) + len(vb)
        blob += kb
        blob += vb

    header = MAGIC.encode("utf-16-le")
    header += struct.pack("<qqqqq", entry_count, HEADER_SIZE, entries_size, data_start, len(blob))
    return bytes(header) + bytes(headers) + bytes(blob)


if __name__ == "__main__":
    import sys
    import json

    path = sys.argv[1]
    with open(path, "rb") as f:
        raw = f.read()
    d = decode(raw)
    print(f"{path}: {len(d)} entries")
    # round-trip self-test
    rebuilt = encode(d)
    d2 = decode(rebuilt)
    assert d2 == d, "round-trip mismatch"
    print("round-trip OK (semantic match; layout is a fresh deterministic rebuild)")
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        print("wrote", sys.argv[2])
