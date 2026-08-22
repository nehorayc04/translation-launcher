#!/usr/bin/env python3
r"""
dsar_write.py — wrap a plain inner PSARC into a Naughty Dog DSAR (DirectStorage/LZ4)
container, the NATIVE archive format of The Last of Us Part II Remastered.

Why DSAR (not the plain PSARC from psarc_write.py): the TLOU2R modding scene's tooling
(ndarc) defaults to DirectStorage/LZ4, the game's own archives are DSAR, and community
guidance says mods should be "LZ4/DirectStorage psarc files". A plain PSAR/zlib mod is
not a confirmed runtime path. So the safe, format-matching mod is DSAR-wrapped. (The
inner archive is still a standard PSARC — build it with psarc_write.build, then wrap here.)

DSAR container (little-endian), the inverse of tools/dsar.py:
  header 0x20:
    0x00  "DSAR" | u16 verMaj(3),verMin(1) | u32 numEntries@0x08 | u32 dataStart@0x0C
    0x10  u64 totalUncompressedSize (= len(inner PSARC)) | 0x18 "PADDING*"
  entry (32 B) x numEntries, sorted by decompOffset (== emission order):
    s64 decompOffset · s64 compOffset(abs) · s32 uncompSize · s32 compSize
    · u8 compType(0=stored, 3=LZ4 block) · 7 reserved (shipping filler 54 55 55 55 55 55 55)
  then the LZ4-block payloads, contiguous, starting at dataStart.
Reader consumes it with lz4.block.decompress(payload, uncompressed_size=uncompSize).

CLI: python dsar_write.py wrap <inner.psarc> <out.psarc>
"""
import os, sys, struct, argparse
import lz4.block

CHUNK = 0x40000                    # 256 KB, matches the shipping DSAR chunking
RESERVED = b"\x54\x55\x55\x55\x55\x55\x55"   # 7-byte filler, exactly as shipped
COMP_LZ4 = 3


def wrap(inner: bytes, chunk=CHUNK) -> bytes:
    n = (len(inner) + chunk - 1) // chunk if inner else 1
    if not inner:
        n = 0
    data_start = 0x20 + n * 32
    entries, payloads = [], bytearray()
    doff, coff = 0, data_start
    for i in range(0, len(inner), chunk):
        raw = inner[i:i + chunk]
        us = len(raw)
        comp = lz4.block.compress(raw, store_size=False)
        if comp is not None and len(comp) < us:
            payload, cs, ctype = comp, len(comp), COMP_LZ4
        else:
            payload, cs, ctype = raw, us, 0             # stored
        entries.append((doff, coff, us, cs, ctype))
        payloads += payload
        doff += us
        coff += cs

    out = bytearray()
    out += b"DSAR" + struct.pack("<HH", 3, 1)
    out += struct.pack("<I", len(entries)) + struct.pack("<I", data_start)
    out += struct.pack("<Q", len(inner))
    out += b"PADDING*"                                   # header is 24 B -> pad to 0x20
    assert len(out) == 0x20, len(out)
    for doff, coff, us, cs, ctype in entries:
        out += struct.pack("<qqii", doff, coff, us, cs) + bytes([ctype]) + RESERVED
    assert len(out) == data_start, (len(out), data_start)
    out += payloads
    return bytes(out)


def _selftest():
    # round-trip through the reader
    HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, HERE)
    import psarc_write, dsar as dsar_reader, io, random
    files = {
        "text2/eng.common": bytes(random.Random(7).randbytes(300000)),
        "fonts/seriffont-Regular.otf": b"OTTO" + bytes(range(256)) * 500,
        "a/b/c.bin": b"hello world",
    }
    inner = psarc_write.build(files)
    dsar_bytes = wrap(inner)
    # write to a temp file and read back through the real reader
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "_dsar_selftest.psarc")
    with open(p, "wb") as f:
        f.write(dsar_bytes)
    ps = dsar_reader.Psarc2(p)
    got = {e.path: ps.extract(e) for e in ps.files()}
    try:
        ps.d.f.close()
        os.remove(p)
    except OSError:
        pass
    ok = got == files
    print(f"wrap->reader round-trip: {'OK' if ok else 'FAIL'}  "
          f"(inner {len(inner):,} -> DSAR {len(dsar_bytes):,} B, {len(files)} files)")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="wrap a plain PSARC into DSAR (DirectStorage/LZ4)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wrap"); w.add_argument("inner"); w.add_argument("out")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "selftest":
        sys.exit(_selftest())
    inner = open(a.inner, "rb").read()
    out = wrap(inner)
    with open(a.out, "wb") as f:
        f.write(out)
    print(f"wrote {a.out}  ({len(out):,} B)")


if __name__ == "__main__":
    main()
