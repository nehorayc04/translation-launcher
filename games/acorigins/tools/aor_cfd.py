#!/usr/bin/env python3
r"""
aor_cfd.py — decode + encode AC Origins CompressedFileData (CFD) blobs.

🔑 ENGINE-FAMILY REUSE: Origins (scimitar v28) uses the SAME CFD container as
AC Shadows (v42) and AC Mirage (v29) — magic 0x1004FA9957FBAA33, 7-byte
CompressionInfo, i32 blockCount, {i32 uncomp, i32 comp} table, then per-block
{u32 adler32(comp,0), bytes}. Validated: 399/399 resources in DataPC.forge
decode with 0 failures using the AC Shadows parser unchanged.

  ⚠️ ODYSSEY DELTA vs Shadows: the game SHIPS ITS OWN `oo2core_4_win64.dll`
  (Oodle 2.4) in the install root — no borrowing needed. And the shipped blocks
  are **Kraken** (decoder_type 6 in byte1), NOT Shadows' Mermaid. Always read the
  codec off `byte1 & 0x7F` of a real block instead of assuming
  ([[oodle-codec-is-byte1-not-byte0]]).

A forge resource blob holds SEVERAL CFDs concatenated: a small metadata CFD then
the object CFD. decode_resource()/encode_resource() handle the list.

    python aor_cfd.py roundtrip <forge> <index>   # decode -> re-encode -> verify
    python aor_cfd.py codec     <forge> <index>   # report the shipped Oodle codec
"""
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

MAGIC = 0x1004FA9957FBAA33
BLOCK = 262144

GAME_DEFAULT = r"F:\Games\Assassin's Creed Origins"

# Oodle compressor ids
OODLE_KRAKEN = 8
OODLE_MERMAID = 9
OODLE_SELKIE = 11
OODLE_LEELA = 12
# byte1 & 0x7F  ->  compressor id  (the ONLY reliable read; byte0 is 0x8C for all)
DECODER_TYPE = {6: OODLE_KRAKEN, 10: OODLE_MERMAID, 11: OODLE_SELKIE, 13: OODLE_LEELA}
NAME = {8: "Kraken", 9: "Mermaid", 11: "Selkie", 12: "Leela"}

_OODLE = None


def oodle():
    """Load the game's OWN oo2core_4_win64.dll (override with ACO_OODLE_DLL)."""
    global _OODLE
    if _OODLE is None:
        dll = os.environ.get("ACO_OODLE_DLL") or os.path.join(
            os.environ.get("ACO_GAME", GAME_DEFAULT), "oo2core_4_win64.dll")
        os.environ.setdefault("ACS_OODLE_DLL", dll)
        from acs_oodle import Oodle
        _OODLE = Oodle(dll if os.path.isfile(dll) else None)
    return _OODLE


def adler(data: bytes) -> int:
    """LZO adler32 = standard Adler-32 with accumulator starting at 0."""
    return zlib.adler32(data, 0) & 0xFFFFFFFF


def sniff_codec(block: bytes):
    """Return (compressor_id, name) read from a real compressed block."""
    if len(block) < 2:
        return None, "?"
    cid = DECODER_TYPE.get(block[1] & 0x7F)
    return cid, NAME.get(cid, f"unknown(byte1=0x{block[1]:02x})")


# --------------------------------------------------------------------- decode
def parse_cfd(buf, off, od=None):
    """Decode one CFD at buf[off]. Returns (data, end_off, cinfo_bytes, codec_id)."""
    od = od or oodle()
    if struct.unpack_from("<Q", buf, off)[0] != MAGIC:
        raise ValueError(f"no CFD magic at 0x{off:x}")
    cinfo = bytes(buf[off + 8:off + 15])            # preserved verbatim on re-encode
    count = struct.unpack_from("<i", buf, off + 15)[0]
    bi = off + 19
    blocks = [struct.unpack_from("<ii", buf, bi + 8 * i) for i in range(count)]
    p = bi + count * 8
    out = bytearray()
    codec = None
    for uncomp, comp in blocks:
        p += 4                                       # stored adler (read + discarded)
        cdata = buf[p:p + comp]
        p += comp
        if comp == uncomp:
            out += cdata
        else:
            if codec is None:
                codec = sniff_codec(cdata)[0]
            out += od.decompress(cdata, uncomp)
    return bytes(out), p, cinfo, codec


def decode_resource(blob, od=None):
    """Decode every CFD in a forge resource. Returns list of (data, cinfo, codec)."""
    od = od or oodle()
    out, off = [], 0
    while off + 8 <= len(blob) and struct.unpack_from("<Q", blob, off)[0] == MAGIC:
        data, off, cinfo, codec = parse_cfd(blob, off, od)
        out.append((data, cinfo, codec))
    return out


def peek_class(blob, od=None):
    """Cheap: decompress ONLY the first block of the LAST CFD -> u32 ScimitarClass
    hash at content[0]. Used to histogram/locate resources without inflating them."""
    od = od or oodle()
    off = 0
    last = None
    while off + 8 <= len(blob) and struct.unpack_from("<Q", blob, off)[0] == MAGIC:
        count = struct.unpack_from("<i", blob, off + 15)[0]
        bi = off + 19
        blocks = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(count)]
        p = bi + count * 8
        last = (p, blocks)
        for uncomp, comp in blocks:
            p += 4 + comp
        off = p
    if not last or not last[1]:
        return None
    p, blocks = last
    uncomp, comp = blocks[0]
    cdata = blob[p + 4:p + 4 + comp]
    head = cdata[:4] if comp == uncomp else od.decompress(cdata, uncomp)[:4]
    if len(head) < 4:
        return None
    return struct.unpack_from("<I", head, 0)[0]


# --------------------------------------------------------------------- encode
def build_cfd(data: bytes, cinfo: bytes, compressor=OODLE_KRAKEN, level=7,
              block=BLOCK, od=None) -> bytes:
    """Re-emit one CFD. cinfo is carried over VERBATIM from the original."""
    od = od or oodle()
    chunks = [data[i:i + block] for i in range(0, len(data), block)] or [b""]
    infos, bodies = [], []
    for ch in chunks:
        c = od.compress(ch, compressor, level)
        if len(c) >= len(ch):                        # STORED when compression loses
            c = ch
        infos.append((len(ch), len(c)))
        bodies.append(c)
    out = bytearray()
    out += struct.pack("<Q", MAGIC)
    out += cinfo
    out += struct.pack("<i", len(chunks))
    for u, c in infos:
        out += struct.pack("<ii", u, c)
    for (u, c), b in zip(infos, bodies):
        out += struct.pack("<I", adler(b))
        out += b
    return bytes(out)


def encode_resource(parts, compressor=OODLE_KRAKEN, level=7, od=None) -> bytes:
    """parts = [(data, cinfo), ...] in original order."""
    od = od or oodle()
    return b"".join(build_cfd(d, ci, compressor, level, od=od) for d, ci in parts)


# ----------------------------------------------------------------------- cli
def _forge(path):
    sys.path.insert(0, HERE)
    import aor_forge
    return aor_forge.Forge(path)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    cmd, path, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
    fg = _forge(path)
    e = fg.entries[idx]
    blob = fg.read(e)
    od = oodle()

    if cmd == "codec":
        parts = decode_resource(blob, od)
        for i, (d, ci, codec) in enumerate(parts):
            print(f"  CFD[{i}] decoded={len(d):,}  cinfo={ci.hex()}  "
                  f"codec={NAME.get(codec, codec)}")
        return 0

    if cmd == "roundtrip":
        parts = decode_resource(blob, od)
        codec = next((c for _, _, c in parts if c), OODLE_KRAKEN)
        re = encode_resource([(d, ci) for d, ci, _ in parts], compressor=codec, od=od)
        back = decode_resource(re, od)
        same = [a[0] for a in parts] == [b[0] for b in back]
        print(f"entry #{idx} id={e.id}  on-disk={len(blob):,}  re-encoded={len(re):,}")
        print(f"  CFDs={len(parts)}  codec={NAME.get(codec, codec)}")
        print(f"  payload round-trip identical: {same}")
        print(f"  byte-identical to disk      : {re == blob}")
        return 0 if same else 1

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
