#!/usr/bin/env python3
r"""
acu_build.py — AC Unity (AnvilNext v27) LocalizationPackage `.data` WRITER.

Given a forge-extracted loc `.data` blob + a {id: new_string} edit map, rebuilds a
valid `.data` the game loads. Pairs with `acu_loc.py` (decode/encode) and
`acu_deploy.py` (forge append-relocate write-back).

`.data` layout (a forge resource IS a `.data`, self-delimiting):
  CFD1(meta) + CFD2(content) + signature
Only the CFD2 content changes (it holds the LocalizationPackage payload). We keep
CFD1 + the signature byte-for-byte, splice the new BE char-index payload into the
content, and re-wrap CFD2 as STORED blocks (uncomp==comp => the game copies them
verbatim; the per-block CRC32 is READ-and-DISCARDED by the engine, so it never
gates loading — we still write a real zlib CRC32 for faithfulness).

The rebuilt loc is ~2x larger than the shipped one because the game's data used a
multi-char (BPE-like) fragment dictionary while AnvilToolkit's encoder (and ours)
uses single-char fragments. That is fine: the resource is relocated to EOF and its
record patched (see acu_deploy.py) — every AC-Unity forge resource is read by its
own record (off + size), so growth/relocation is safe.

VALIDATED 2026-07-01: identity rebuild of TLocalizationPackage_English round-trips
to the same 8,999 strings (0 mismatches); single-string edits apply cleanly with
every other string intact.
"""
import struct
import zlib
import sys

from acu_loc import cfd_decompress, decode_payload, encode_payload, _payload_from_data  # noqa

_MAGIC = 0x1004FA9957FBAA33


def split_cfds(data):
    """`.data` -> (p1_end_of_cfd1, cfd1_meta, p2_end_of_cfd2, cfd2_content, signature)."""
    p1, meta = cfd_decompress(data, 0)
    p2, content = cfd_decompress(data, p1)
    return p1, meta, p2, content, data[p2:]


def find_payload_pos(content):
    """Locate the LocalizationPackage payload inside CFD2 content -> (count_pos, old_count)."""
    body_off = 12 + struct.unpack_from("<i", content, 8)[0]      # skip id,count,namelen,name
    for off in range(body_off, body_off + 96):
        v = struct.unpack_from("<i", content, off)[0]
        if 1000 < v < len(content) - off and content[off + 4] == 0 and 128 <= content[off + 5] <= 255:
            return off, v
    raise ValueError("LocalizationPackage payload not found in content")


def make_cfd_stored(content, compinfo7):
    """Wrap `content` as one CompressedFileData with STORED blocks. `compinfo7` = the
    original CFD's 7-byte CompressionInfo header (ver i16, algo u8, maxU u16, maxC u16)."""
    maxU = struct.unpack_from("<H", compinfo7, 3)[0]
    blk = min(maxU if maxU else 0xFFF0, 0xFFF0)                  # u16 block-size ceiling
    out = bytearray()
    out += struct.pack("<Q", _MAGIC)
    out += compinfo7
    blocks = [content[i:i + blk] for i in range(0, len(content), blk)] or [b""]
    out += struct.pack("<i", len(blocks))                       # Unity: i32 block count
    for b in blocks:
        out += struct.pack("<HH", len(b), len(b))               # [uncomp, comp] LE, equal => stored
    for b in blocks:
        out += struct.pack("<I", zlib.crc32(b) & 0xffffffff)    # per-block CRC (engine ignores it)
        out += b
    return bytes(out)


def build_loc_data(orig_data, new_strings):
    """orig `.data` bytes + {id:str} -> rebuilt `.data` bytes (STORED, game-loadable)."""
    p1, _meta, _p2, content, sig = split_cfds(orig_data)
    P, old_count = find_payload_pos(content)
    new_payload = encode_payload(new_strings, maxIndex=255)
    new_content = content[:P] + struct.pack("<i", len(new_payload)) + new_payload + content[P + 4 + old_count:]
    compinfo7 = orig_data[p1 + 8:p1 + 15]
    return orig_data[:p1] + make_cfd_stored(new_content, compinfo7) + sig


def verify_decodes_to(data, expected):
    """Assert a rebuilt `.data` decodes back to `expected` {id:str}. Returns mismatch count."""
    got = decode_payload(_payload_from_data(data)[1])
    return sum(1 for k in expected if expected.get(k) != got.get(k)), len(got)


if __name__ == "__main__":
    import json
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = __import__("argparse").ArgumentParser(description="AC Unity loc .data writer")
    ap.add_argument("orig_data", help="forge-extracted loc .data (e.g. extract/loc_english.bin)")
    ap.add_argument("out_data", help="output rebuilt .data")
    ap.add_argument("--edits", help="JSON {id: hebrew_or_latin} to apply (visual reversal NOT applied here)")
    a = ap.parse_args()
    orig = open(a.orig_data, "rb").read()
    strings = decode_payload(_payload_from_data(orig)[1])
    print(f"orig: {len(strings)} strings, {len(orig):,} B")
    edited = dict(strings)
    if a.edits:
        em = json.load(open(a.edits, encoding="utf-8"))
        for k, v in em.items():
            edited[int(k)] = v
        print(f"applied {len(em)} edits")
    new = build_loc_data(orig, edited)
    open(a.out_data, "wb").write(new)
    mism, n = verify_decodes_to(new, edited)
    print(f"wrote {a.out_data}: {len(new):,} B (delta {len(new)-len(orig):+,})  re-decode: {n} strings, {mism} mismatches")
