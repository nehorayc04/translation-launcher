"""
gl_rpkg_write.py — build a Glacier RPKG v2 PATCH archive ("chunkNpatchM.rpkg")
that overrides a set of resources by hash, in pure Python.

Layout (patch, from RPKG-Tool first-light generate_rpkg_from.cpp + import_rpkg.cpp, verified):
  header (29 bytes): "2KPR" + 9 v2-header bytes + u32 hash_count + u32 table_offset(=count*0x14)
                     + u32 table_size(=sum of meta-entry bytes) + u32 patch_count
  patch_count x u64  deletion hash list (0 here — override-only patch)
  file table 1: hash_count x { u64 hash ; u64 abs_offset ; u32 data_size }
  file table 2: hash_count x <verbatim metadata entry> (size_final @+8 patched to the new length)
  data:         each override, LZ4-compressed (raw block) then XORed => data_size = comp | 0x80000000

`hash_offset` (data start) for a v2 patch = table_offset + table_size + patch_count*8 + 0x1D
(0x1D = 29), exactly generate_rpkg_from's formula. Each override is stored in the SAME form the
base uses for LOCR/GFXF (100% LZ4+XORed) and that every RPKG-Tool-built mod ships: LZ4 raw block
+ XOR, data_size = compressed_size | 0x80000000. The engine un-XORs then LZ4-decompresses to
size_final. size_final (in the meta) = the raw/decompressed length.

The metadata entry is copied verbatim from the base resource (preserving type + references),
with only size_final (@ +8) patched to len(new_bytes).
"""
import struct
import os
import sys
import lz4.block

sys.path.insert(0, os.path.dirname(__file__))
from gl_rpkg import RPKG, MAGIC, xor_data

XOR_FLAG = 0x80000000   # data_size bit31 = XORed


def _encode_resource(raw: bytes, lz4ed: bool = True):
    """Return (on_disk_bytes, data_size_field) matching the base's proven store form.
    lz4ed=True  -> LZ4 raw block + XOR, data_size = comp_size | 0x80000000  (LOCR/GFXF form)
    lz4ed=False -> stored + XOR,        data_size = 0x80000000               (TEXT form)"""
    if lz4ed:
        comp = lz4.block.compress(raw, store_size=False)   # raw LZ4 block, no 4-byte size prefix
        on_disk = bytes(xor_data(bytearray(comp)))
        return on_disk, (len(comp) & 0x3FFFFFFF) | XOR_FLAG
    on_disk = bytes(xor_data(bytearray(raw)))
    return on_disk, XOR_FLAG


def build_patch(base: RPKG, overrides: dict, out_path: str, deletions=None, lz4ed=True):
    """overrides: {hash:int -> new_decompressed_bytes}.  deletions: optional list[hash].
    Each override is encoded like the base (LZ4+XOR by default — the universal Glacier-mod form)."""
    deletions = deletions or []
    entries = []  # (hash, on_disk_bytes, meta_bytes, data_size_field)
    for hsh, new_data in overrides.items():
        r = base.by_hash(hsh)
        if r is None:
            raise KeyError(f"hash {hsh:016X} not in base archive")
        meta = bytearray(r.raw_meta)
        struct.pack_into("<I", meta, 8, len(new_data))     # size_final := new (raw) length
        on_disk, dsz = _encode_resource(bytes(new_data), lz4ed=lz4ed)
        entries.append((hsh, on_disk, bytes(meta), dsz))

    hash_count = len(entries)
    table_offset = hash_count * 0x14                        # file table 1 size
    table_size = sum(len(m) for _, _, m, _ in entries)      # file table 2 size
    patch_count = len(deletions)
    body_start = 29 + patch_count * 8
    data_start = body_start + table_offset + table_size

    out = bytearray()
    out += MAGIC
    out += base.v2_header
    out += struct.pack("<III", hash_count, table_offset, table_size)
    out += struct.pack("<I", patch_count)
    for h in deletions:
        out += struct.pack("<Q", h)

    # file table 1 (absolute offsets)
    off = data_start
    for hsh, data, meta, dsz in entries:
        out += struct.pack("<QQI", hsh, off, dsz)
        off += len(data)
    # file table 2 (verbatim meta)
    for _, _, meta, _ in entries:
        out += meta
    # data
    for _, data, _, _ in entries:
        out += data

    assert len(out) == data_start + sum(len(d) for _, d, _, _ in entries)
    with open(out_path, "wb") as f:
        f.write(out)
    return out_path


def _selftest():
    """Identity round-trip: take a few real LOCRs from chunk0, build a patch that re-encodes
    their ORIGINAL decompressed bytes (LZ4+XOR), re-read the patch, confirm byte-identical."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("rpkg")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--stored", action="store_true", help="test the stored (non-LZ4) form")
    a = ap.parse_args()
    base = RPKG(a.rpkg)
    idxs = base.indices("LOCR")[:a.n]
    overrides = {}
    originals = {}
    for i in idxs:
        r = base.resources[i]
        data = base.read(i)
        overrides[r.hash] = data
        originals[r.hash] = data
    out = "C:/tmp/chunk0patchTEST.rpkg"
    build_patch(base, overrides, out, lz4ed=not a.stored)
    sz = os.path.getsize(out)
    print(f"built patch {out}  ({sz} bytes, {len(overrides)} resources, "
          f"form={'STORED' if a.stored else 'LZ4'}+XOR)")
    patch = RPKG(out, is_patch=True)
    print(f"re-read: file_count={patch.file_count} patch_count={patch.patch_count} "
          f"meta_valid={patch._t2_valid}")
    ok = 0
    for hsh, orig in originals.items():
        got = patch.read_hash(hsh)
        r = patch.by_hash(hsh)
        match = (got == orig and r.rtype == "LOCR" and r.size_final == len(orig))
        ok += match
        if not match:
            print(f"  MISMATCH {hsh:016X}: type={r.rtype} sf={r.size_final} "
                  f"len={len(got)} vs {len(orig)}")
    print(f"identity round-trip: {ok}/{len(originals)} resources byte-identical + meta correct")


if __name__ == "__main__":
    _selftest()
