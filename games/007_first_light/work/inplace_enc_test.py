"""
inplace_enc_test.py — decisive isolation test: edit ONE LOCR resource IN PLACE inside
chunk0.rpkg (a valid BASE archive), with NO patch file and NO packagedefinition change.

This isolates the RESOURCE ENCODING (my LZ4-HC + XOR + meta) from the PATCH STRUCTURE.
Every patch test crashed; the base (chunk0) loads fine. If a surgical in-place base edit
with MY encoding boots and shows the marker -> my encoding is engine-valid and the patch
FORMAT is the sole bug. If it crashes -> my LZ4/XOR/meta encoding itself is wrong.

Mechanism (same-or-smaller edit, so zero structural change):
  - replace one menu string with a short pure-Latin marker (compresses smaller -> fits)
  - LZ4-HC compress + XOR the new LOCR bytes
  - overwrite the resource bytes in place (leftover original bytes become a harmless gap)
  - patch table1.data_size and table2.size_final (both at known file offsets)
  - back up the exact original bytes for a perfect revert

Run:  python inplace_enc_test.py deploy   (launch game -> main menu, report)
      python inplace_enc_test.py revert
"""
import os
import sys
import json
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from gl_rpkg import RPKG, xor_data
import gl_locr as L
import lz4.block

GAME = r"F:\Game Lab\007 First Light"
CHUNK0 = os.path.join(GAME, "Runtime", "chunk0.rpkg")
BACKUP = os.path.join(HERE, "inplace_enc_backup.json")

LOCR_HASH = 0x01C76A08493EEE11     # menu LOCR (Continue etc.)
LINE_HASH = 0xB3597EF8             # "Continue"
MARKER = "ZZ-007-INPLACE-OK"       # pure-Latin -> no font dependency, proves the edit loads


def _field_offsets(R, i):
    body_start = 25
    t1_dsize_off = body_start + i * 20 + 16
    t2_start = body_start + R.table_offset
    cum = sum(len(R.resources[k].raw_meta) for k in range(i))
    meta_off = t2_start + cum
    return t1_dsize_off, meta_off + 8


def deploy():
    if os.path.exists(BACKUP):
        print("  backup already exists -> revert first"); return
    R = RPKG(CHUNK0)
    i = R._by_hash[LOCR_HASH]
    r = R.resources[i]
    orig_comp = r.comp_size

    # decode, edit ONE line to the Latin marker, re-encode the LOCR
    ver, langs = L.decode_locr(R.read(i))
    n = 0
    for block in langs:
        if not block:
            continue
        for j, (h, s) in enumerate(block):
            if h == LINE_HASH:
                block[j] = (h, MARKER); n += 1
    new_content = L.encode_locr(langs, version=ver)
    print(f"  patched {n} slots of line {LINE_HASH:08X} -> '{MARKER}'  new size_final={len(new_content)}")

    # LZ4-HC + XOR (the base's proven form)
    comp = lz4.block.compress(new_content, mode='high_compression', compression=12, store_size=False)
    if len(comp) > orig_comp:
        print(f"  ABORT: re-encoded {len(comp)} > original {orig_comp} (won't fit in place)"); return
    on_disk = bytes(xor_data(bytearray(comp)))
    new_dsize = (len(comp) & 0x3FFFFFFF) | 0x80000000

    t1_dsize_off, sf_off = _field_offsets(R, i)

    # back up the exact bytes we will change
    with open(CHUNK0, "r+b") as f:
        f.seek(r.offset); orig_bytes = f.read(orig_comp)
        f.seek(t1_dsize_off); orig_dsize = f.read(4)
        f.seek(sf_off); orig_sf = f.read(4)
        json.dump({
            "offset": r.offset, "orig_comp": orig_comp,
            "orig_bytes_hex": orig_bytes.hex(),
            "t1_dsize_off": t1_dsize_off, "orig_dsize_hex": orig_dsize.hex(),
            "sf_off": sf_off, "orig_sf_hex": orig_sf.hex(),
        }, open(BACKUP, "w"))
        # write the new resource bytes in place (leftover original bytes = harmless gap)
        f.seek(r.offset); f.write(on_disk)
        f.seek(t1_dsize_off); f.write(struct.pack("<I", new_dsize))
        f.seek(sf_off); f.write(struct.pack("<I", len(new_content)))
    print(f"  wrote {len(on_disk)} bytes @ {r.offset} (gap {orig_comp - len(on_disk)}), "
          f"data_size={new_dsize:#x}, size_final={len(new_content)}")
    print("DEPLOYED (in-place base edit, NO patch, NO packagedefinition change).")
    print("Launch the game -> main menu. If 'Continue' shows 'ZZ-007-INPLACE-OK' => my LOCR "
          "encoding is engine-valid and the PATCH FORMAT is the bug. If it crashes => my "
          "encoding (LZ4/XOR/meta) is the bug.")


def revert():
    if not os.path.exists(BACKUP):
        print("  no backup"); return
    b = json.load(open(BACKUP))
    with open(CHUNK0, "r+b") as f:
        f.seek(b["offset"]); f.write(bytes.fromhex(b["orig_bytes_hex"]))
        f.seek(b["t1_dsize_off"]); f.write(bytes.fromhex(b["orig_dsize_hex"]))
        f.seek(b["sf_off"]); f.write(bytes.fromhex(b["orig_sf_hex"]))
    os.remove(BACKUP)
    print("REVERTED (chunk0 restored byte-for-byte).")


if __name__ == "__main__":
    {"deploy": deploy, "revert": revert}[sys.argv[1]]()
