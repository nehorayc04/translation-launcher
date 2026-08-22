#!/usr/bin/env python3
"""
acs_cfd.py — decode + ENCODE AC Shadows CompressedFileData (CFD) blobs.

Implements the cracked v42 format (see ../FORMAT.md), verified against
DataPC_boot.forge resource 36626 (per-block Adler-32 matches byte-for-byte):

  u64 Magic = 0x1004FA9957FBAA33
  CompressionInfo[7]  (i16 ver=3, u8 algo=8, u16 maxUncomp, u16 maxComp)
  i32 blockCount
  BlockInfoData : blockCount x { i32 uncompressedSize, i32 compressedSize }
  CompressedData: blockCount x { u32 adler=zlib.adler32(comp,0), u8[comp] }

A forge resource blob may hold SEVERAL CFDs concatenated (e.g. a small metadata
CFD then the big data CFD); decode_resource()/encode_resource() handle the list.

    python acs_cfd.py roundtrip <forge> <index>   # decode->re-encode->verify
"""
import sys
import os
import struct
import zlib

MAGIC = 0x1004FA9957FBAA33
BLOCK = 262144


def _oodle():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from acs_oodle import Oodle
    return Oodle()


def adler(data: bytes) -> int:
    """LZO adler32 = standard Adler-32 with accumulator starting at 0."""
    return zlib.adler32(data, 0) & 0xFFFFFFFF


def parse_cfd(buf, off, oodle):
    """Decode one CFD at buf[off]. Returns (data, end_off, cinfo_bytes)."""
    if struct.unpack_from("<Q", buf, off)[0] != MAGIC:
        raise ValueError(f"no CFD magic at 0x{off:x}")
    cinfo = bytes(buf[off + 8:off + 15])          # preserved verbatim
    count = struct.unpack_from("<i", buf, off + 15)[0]
    bi = off + 19
    blocks = [struct.unpack_from("<ii", buf, bi + 8 * i) for i in range(count)]  # (uncomp, comp)
    p = bi + count * 8
    out = bytearray()
    for uncomp, comp in blocks:
        p += 4                                     # skip stored adler
        cdata = buf[p:p + comp]
        p += comp
        out += cdata if comp == uncomp else oodle.decompress(cdata, uncomp)
    return bytes(out), p, cinfo


# AC Shadows compresses with MERMAID (OodleLZ_Compressor 9) at level 7, NOT Kraken.
# Proven: Mermaid@7 reproduces the game's own blocks BYTE-IDENTICALLY, 8/8 tested
# (145,337 / 150,501 / 207,798 / 119,468 / 144,139 / 118,119 / 210,272 / 171,137).
#
# This was the crash. byte0 of an Oodle chunk is 0x8C for every LZ compressor -- it
# only says "Oodle LZ" -- and the actual codec lives in `byte1 & 0x7F`:
#     game   8c 0a ...  -> decoder_type 10 = Mermaid
#     Kraken 8c 06 ...  -> decoder_type 6
# Writing Kraken produced a stream this engine will not decode, so every re-encoded
# LocalizationPackage crashed the moment the menu read it. (Resources that are NOT
# read at boot -- e.g. the `loc` dialogue type -- "worked" only because nothing ever
# decoded them.) It also explains the ~5% smaller output that looked like a free win
# and drove the "re-pack the forge" plan: Kraken simply compresses harder than
# Mermaid. Match the codec and the natural re-encode lands on the vanilla size.
MERMAID = 9
LEVEL = 7


def build_cfd(data, cinfo, oodle, level=LEVEL, compressor=MERMAID):
    """Encode raw `data` into a CFD blob (Mermaid; raw-store when it doesn't shrink)."""
    n = len(data)
    nblocks = max(1, (n + BLOCK - 1) // BLOCK)
    blockinfo = bytearray()
    compdata = bytearray()
    for i in range(nblocks):
        raw = data[i * BLOCK:(i + 1) * BLOCK]
        comp = oodle.compress(raw, compressor=compressor, level=level)
        if len(comp) >= len(raw):                  # didn't help -> store raw
            comp = raw
        blockinfo += struct.pack("<ii", len(raw), len(comp))
        compdata += struct.pack("<I", adler(comp)) + comp
    out = bytearray()
    out += struct.pack("<Q", MAGIC)
    out += cinfo
    out += struct.pack("<i", nblocks)
    out += blockinfo
    out += compdata
    return bytes(out)


def decode_resource(blob, oodle=None):
    """Decode every CFD in a resource blob -> list of (data, cinfo)."""
    oodle = oodle or _oodle()
    cfds = []
    off = 0
    n = len(blob)
    while off + 8 <= n and struct.unpack_from("<Q", blob, off)[0] == MAGIC:
        data, off, cinfo = parse_cfd(blob, off, oodle)
        cfds.append((data, cinfo))
    return cfds, off


def cmd_roundtrip(forge, index):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F
    o = _oodle()
    info = F.parse(forge)
    r = info["recs"][index]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    cfds, consumed = decode_resource(blob, o)
    total = sum(len(d) for d, _ in cfds)
    print(f"resource {index}: {len(cfds)} CFD(s), decoded {total:,} bytes, "
          f"consumed 0x{consumed:x}/0x{r['size']:x}")
    # re-encode each CFD and verify it decodes back to the same data
    ok = 0
    for i, (data, cinfo) in enumerate(cfds):
        blob2 = build_cfd(data, cinfo, o)
        back, _, _ = parse_cfd(blob2, 0, o)
        same = back == data
        ok += same
        print(f"  CFD{i}: {len(data):,} B -> re-encoded {len(blob2):,} B "
              f"({len(blob2)/max(1,len(data)):.2f}x) -> round-trip {'OK' if same else 'FAIL'}")
    print(f"round-trip: {ok}/{len(cfds)} CFDs reproduce identically")
    return 0 if ok == len(cfds) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 4 and sys.argv[1] == "roundtrip":
        sys.exit(cmd_roundtrip(sys.argv[2], int(sys.argv[3])))
    print(__doc__)
