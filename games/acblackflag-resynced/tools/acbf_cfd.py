#!/usr/bin/env python3
"""
acbf_cfd.py -- decode + encode AC Black Flag Resynced (scimitar-v50)
CompressedFileData (CFD) resource blobs.

Ported from the AC Shadows v42 codec (acs_cfd.py) — the CFD format is UNCHANGED
in v50 (verified: the English FADE9F44 loc + the multi-block char-index loc both
decode with it):

  u64  Magic = 0x1004FA9957FBAA33          (bytes 33 aa fb 57 99 fa 04 10)
  u8[7] CompressionInfo                    (preserved verbatim on re-encode)
  i32  blockCount
  BlockInfoData : blockCount x { i32 uncompressedSize, i32 compressedSize }
  CompressedData: blockCount x { u32 adler = zlib.adler32(comp,0), u8[comp] }

A resource blob may hold SEVERAL CFDs concatenated (a small metadata CFD then a
big data CFD) — decode_resource()/encode_resource() walk the list.

⚠️ THE bug this fixes: a naive "each 0x57FBAA33 is an independent 0x1F-header
chunk" walk only works for a SINGLE-block CFD. A multi-block CFD puts ALL block
sizes in one table BEFORE the payloads, so the naive walk misreads block 1's
info as block 0's payload and stops early — which hid the multi-language
char-index localization.
"""
import sys
import os
import struct
import zlib

MAGIC = 0x1004FA9957FBAA33
BLOCK = 262144


def _oodle():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "acshadows", "tools"))
    os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")
    from acs_oodle import Oodle
    return Oodle()


def adler(data: bytes) -> int:
    return zlib.adler32(data, 0) & 0xFFFFFFFF


def parse_cfd(buf, off, oodle):
    """Decode one CFD at buf[off]. Returns (data, end_off, cinfo_bytes)."""
    if off + 19 > len(buf) or struct.unpack_from("<Q", buf, off)[0] != MAGIC:
        raise ValueError(f"no CFD magic at 0x{off:x}")
    cinfo = bytes(buf[off + 8:off + 15])
    count = struct.unpack_from("<i", buf, off + 15)[0]
    if count < 1 or count > 200000:
        raise ValueError(f"bad blockCount {count}")
    bi = off + 19
    blocks = [struct.unpack_from("<ii", buf, bi + 8 * i) for i in range(count)]
    p = bi + count * 8
    out = bytearray()
    for uncomp, comp in blocks:
        p += 4                                      # skip stored adler
        cdata = buf[p:p + comp]
        p += comp
        out += cdata if comp == uncomp else oodle.decompress(cdata, uncomp)
    return bytes(out), p, cinfo


def build_cfd(data, cinfo, oodle, level=4):
    n = len(data)
    nblocks = max(1, (n + BLOCK - 1) // BLOCK)
    blockinfo = bytearray()
    compdata = bytearray()
    for i in range(nblocks):
        raw = data[i * BLOCK:(i + 1) * BLOCK]
        comp = oodle.compress(raw, level=level)
        if len(comp) >= len(raw):
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


def build_cfd_exact(core, cinfo, oodle, target_ondisk, level=7, at4=True):
    """Build ONE CFD whose ON-DISK size == target_ondisk EXACTLY, holding `core`
    (a bytearray) as its decoded data plus a trailing RAW-zero pad block.

    Why: a v50 resource's CFDs fill its TOC `size` EXACTLY, and shrinking that
    size (leaving a gap) breaks the game's contiguous/DirectStorage loading
    (black screen). So we must keep the resource the ORIGINAL byte size — but our
    Oodle compresses the (Hebrew) payload smaller. We top it up with a final RAW
    block of zeros so 2 CFDs still fill the exact original size, and the trailing
    zeros sit AFTER the single LocalizationPackage (read by `num`, so ignored).

    `at4`: keep the object-size field at core[4:8] == (final decoded len - 51)
    (the invariant every native CFD1 satisfies), re-deriving it as the pad grows.
    Returns (cfd_bytes, decoded_len). decoded_len = len(core) + pad_len.
    """
    core = bytearray(core)
    n = len(core)
    nblocks = max(1, (n + BLOCK - 1) // BLOCK)
    blockinfo = bytearray(); compdata = bytearray()
    for i in range(nblocks):
        raw = bytes(core[i * BLOCK:(i + 1) * BLOCK])
        comp = oodle.compress(raw, level=level)
        if len(comp) >= len(raw):
            comp = raw
        blockinfo += struct.pack("<ii", len(raw), len(comp))
        compdata += struct.pack("<I", adler(comp)) + comp
    base = 8 + 7 + 4 + len(blockinfo) + len(compdata)       # on-disk without pad
    pad_len = target_ondisk - base - 12                     # one raw pad block adds 12+pad_len
    if pad_len < 0:
        raise ValueError(f"core compresses to {base} > target {target_ondisk-12} (no room to pad)")
    if pad_len > BLOCK:
        raise ValueError(f"pad_len {pad_len} > {BLOCK} (multi-block pad not implemented)")
    decoded_len = n + pad_len
    # NB: @4 (object size) stays what the caller set on `core` (= real object size,
    # len(core)-51). The pad is dead trailing space in the decompressed CFD1 buffer,
    # sized via CFD0@10 = decoded_len (set by the caller). at4 is unused (kept for API).
    out = bytearray()
    out += struct.pack("<Q", MAGIC) + cinfo + struct.pack("<i", nblocks + 1)
    out += blockinfo
    out += struct.pack("<ii", pad_len, pad_len)             # pad blockinfo (raw: comp==uncomp)
    out += compdata
    pad = b"\x00" * pad_len
    out += struct.pack("<I", adler(pad)) + pad
    assert len(out) == target_ondisk, f"{len(out)} != {target_ondisk}"
    return bytes(out), decoded_len


def _incompressible(n, seed=b"acbf-pad-v1"):
    """Deterministic, incompressible, MARKER-FREE filler of length n (SHA-256 keystream
    with any 0xD28389B5 LocalizationPackage marker broken)."""
    import hashlib
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hashlib.sha256(seed + ctr.to_bytes(8, "little")).digest()
        ctr += 1
    out = out[:n]
    mk = struct.pack("<I", 0xD28389B5)
    i = 0
    while n >= 4:
        j = bytes(out).find(mk, i)
        if j < 0:
            break
        out[j] ^= 0xFF
        i = j + 1
    return bytes(out)


def build_cfd_object_to_size(object_core, cinfo, oodle, target_ondisk, level=7, keep_at4=False):
    """Build ONE CFD holding a loc OBJECT, whose ON-DISK size == target_ondisk EXACTLY,
    the NATIVE way: append an incompressible pad to the object so the object grows and
    NATURAL 262144-block splitting + compression lands on `target_ondisk` — keeping the
    native block count (no extra raw pad block).

    keep_at4=False: set @4 = decoded_len-51 (invariant CFD0@10==@4+51 holds; the pad is
      INSIDE the declared object, after the single package).
    keep_at4=True:  leave @4 as-is (= the REAL object size); the pad sits OUTSIDE the
      declared object (in the decompressed buffer beyond @4). Buffer > object.

    Pad is marker-free so no phantom package is scanned. Returns (cfd_bytes, decoded_len)."""
    object_core = bytearray(object_core)
    base_obj_len = len(object_core)

    def blocks(data):
        nb = max(1, (len(data) + BLOCK - 1) // BLOCK)
        bi = bytearray(); cd = bytearray()
        for i in range(nb):
            raw = data[i * BLOCK:(i + 1) * BLOCK]
            comp = oodle.compress(bytes(raw), level=level)
            if len(comp) >= len(raw):
                comp = bytes(raw)
            bi += struct.pack("<ii", len(raw), len(comp))
            cd += struct.pack("<I", adler(comp)) + comp
        return 8 + 7 + 4 + len(bi) + len(cd), nb, bi, cd

    base0, _, _, _ = blocks(bytes(object_core))
    est = target_ondisk - base0                      # incompressible pad is ~1:1 on disk
    for pad_len in sorted(range(max(0, est - 64), est + 65), key=lambda p: abs(p - est)):
        if not keep_at4:
            struct.pack_into("<I", object_core, 4, (base_obj_len + pad_len - 51) & 0xFFFFFFFF)
        data = bytes(object_core) + _incompressible(pad_len)
        ondisk, nb, bi, cd = blocks(data)
        if ondisk == target_ondisk:
            out = struct.pack("<Q", MAGIC) + cinfo + struct.pack("<i", nb) + bi + cd
            assert len(out) == target_ondisk
            return bytes(out), len(data)
    raise RuntimeError(f"build_cfd_object_to_size: no pad in [{est-64},{est+64}] hit {target_ondisk}")


def decode_resource(blob, oodle=None):
    """Decode every CFD in a resource blob -> (list[(data,cinfo)], consumed)."""
    oodle = oodle or _oodle()
    cfds = []
    off = 0
    n = len(blob)
    while off + 8 <= n and struct.unpack_from("<Q", blob, off)[0] == MAGIC:
        data, off, cinfo = parse_cfd(blob, off, oodle)
        cfds.append((data, cinfo))
    return cfds, off


def decode_all(blob, oodle=None):
    """Convenience: concatenated decompressed bytes of every CFD in a blob."""
    cfds, _ = decode_resource(blob, oodle)
    return b"".join(d for d, _ in cfds)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 4 and sys.argv[1] == "roundtrip":
        import importlib.util
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acbf_forge.py")
        s = importlib.util.spec_from_file_location("acbf_forge", p); AF = importlib.util.module_from_spec(s); s.loader.exec_module(AF)
        o = _oodle()
        info = AF.parse(sys.argv[2]); r = info["recs"][int(sys.argv[3])]
        with open(sys.argv[2], "rb") as f:
            f.seek(r["offset"]); blob = f.read(r["size"])
        cfds, consumed = decode_resource(blob, o)
        total = sum(len(d) for d, _ in cfds)
        print(f"resource {sys.argv[3]}: {len(cfds)} CFD(s), decoded {total:,} B, "
              f"consumed 0x{consumed:x}/0x{r['size']:x}")
        ok = 0
        for i, (data, cinfo) in enumerate(cfds):
            b2 = build_cfd(data, cinfo, o)
            back, _, _ = parse_cfd(b2, 0, o)
            same = back == data; ok += same
            print(f"  CFD{i}: {len(data):,} B -> {len(b2):,} B round-trip {'OK' if same else 'FAIL'}")
        print(f"round-trip {ok}/{len(cfds)}")
    else:
        print(__doc__)
