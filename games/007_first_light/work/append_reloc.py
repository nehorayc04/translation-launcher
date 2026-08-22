"""
append_reloc.py — DEPLOY mechanism for 007 First Light that sidesteps the (still-broken)
patch-RPKG format entirely.

The in-place base edit proved my LOCR encoding is engine-valid and that chunk0 loads with a
surgically edited resource. This generalises it to ANY size (grow or shrink):

  For each overridden resource:
    1. LZ4-HC + XOR the new bytes.
    2. APPEND them at the END of chunk0.rpkg (grows the file; old bytes become a dead gap).
    3. Repoint that resource's table-1 data_offset  -> the new EOF location.
    4. Patch table-1 data_size  and  table-2 size_final.
  The header, tables, and every other resource stay byte-identical, so the engine still parses
  chunk0 as the valid base it already loads — it just reads these few resources from EOF.

Reversible: the original table fields are saved and the appended bytes truncated on revert.
NO patch file, NO packagedefinition change. chunk0 is the only file touched (backed up fields).
"""
import os
import sys
import json
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from gl_rpkg import RPKG, xor_data
import lz4.block

GAME = r"F:\Game Lab\007 First Light"
CHUNK0 = os.path.join(GAME, "Runtime", "chunk0.rpkg")
BACKUP = os.path.join(HERE, "append_reloc_backup.json")


def _encode(raw: bytes):
    comp = lz4.block.compress(raw, mode="high_compression", compression=12, store_size=False)
    return bytes(xor_data(bytearray(comp))), (len(comp) & 0x3FFFFFFF) | 0x80000000


def _sf_off(R, i):
    return 25 + R.table_offset + sum(len(R.resources[k].raw_meta) for k in range(i)) + 8


def deploy(overrides: dict, target=CHUNK0, backup_path=BACKUP):
    """overrides: {resource_hash:int -> new_decompressed_bytes}."""
    if os.path.exists(backup_path):
        print("  backup exists -> revert first"); return
    R = RPKG(target)
    orig_size = os.path.getsize(target)
    bk = {"target": target, "orig_size": orig_size, "entries": []}
    with open(target, "r+b") as f:
        for h, raw in overrides.items():
            i = R._by_hash[h]
            t1 = 25 + i * 20
            sf = _sf_off(R, i)
            f.seek(t1 + 8);  orig_off  = f.read(8)
            f.seek(t1 + 16); orig_ds   = f.read(4)
            f.seek(sf);      orig_sf   = f.read(4)
            on_disk, dsize = _encode(raw)
            f.seek(0, 2); new_off = f.tell(); f.write(on_disk)
            f.seek(t1 + 8);  f.write(struct.pack("<Q", new_off))
            f.seek(t1 + 16); f.write(struct.pack("<I", dsize))
            f.seek(sf);      f.write(struct.pack("<I", len(raw)))
            bk["entries"].append({
                "hash": h, "t1": t1, "sf": sf,
                "orig_off": orig_off.hex(), "orig_ds": orig_ds.hex(), "orig_sf": orig_sf.hex(),
            })
            print(f"  {h:016X} idx={i}: appended {len(on_disk)}B @ {new_off} "
                  f"(size_final={len(raw)}, data_size={dsize:#x})")
    json.dump(bk, open(backup_path, "w"))
    print(f"DEPLOYED via append-relocate ({len(overrides)} resources). File grew "
          f"{os.path.getsize(target) - orig_size} B.")


def revert(backup_path=BACKUP):
    if not os.path.exists(backup_path):
        print("  no backup"); return
    bk = json.load(open(backup_path))
    with open(bk["target"], "r+b") as f:
        for e in bk["entries"]:
            f.seek(e["t1"] + 8);  f.write(bytes.fromhex(e["orig_off"]))
            f.seek(e["t1"] + 16); f.write(bytes.fromhex(e["orig_ds"]))
            f.seek(e["sf"]);      f.write(bytes.fromhex(e["orig_sf"]))
        f.truncate(bk["orig_size"])
    os.remove(backup_path)
    print("REVERTED (chunk0 fields restored + file truncated).")


# ---- standalone sanity: append-relocate a single visible menu string to a Latin marker ----
if __name__ == "__main__":
    import gl_locr as L
    OPT_LOCR = 0x01B4B8D71B46C3B8
    OPT_LINE = 0x023510F0          # "Options"
    MARKER = "ZZ-APPEND-OK"
    if sys.argv[1] == "deploy":
        R = RPKG(CHUNK0)
        ver, langs = L.decode_locr(R.read(R._by_hash[OPT_LOCR]))
        n = 0
        for block in langs:
            for j, (h, s) in enumerate(block or []):
                if h == OPT_LINE:
                    block[j] = (h, MARKER); n += 1
        print(f"  patched {n} slots -> '{MARKER}'")
        deploy({OPT_LOCR: L.encode_locr(langs, version=ver)})
        print("Launch -> main menu. If 'OPTIONS' now reads 'ZZ-APPEND-OK', append-relocate "
              "WORKS and is our deploy mechanism.")
    else:
        revert()
