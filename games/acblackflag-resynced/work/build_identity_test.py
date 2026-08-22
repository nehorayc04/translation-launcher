#!/usr/bin/env python3
"""
IDENTITY ISOLATION TEST for the "warning window + crash".

Re-deploy the Arabic-UI resource with the ORIGINAL Arabic payload VERBATIM (no
Hebrew, no flat-leaf re-encode) — only the OUTER wrapper is rebuilt: our Oodle
re-compresses the (byte-identical) decoded CFDs, and the TOC size field is shrunk
to fit in-place.  This isolates the two remaining suspects:

  * Arabic renders fine  -> Oodle re-compress + write-mechanism are OK
                            => the flat-leaf ENCODER (build_payload) is the bug.
  * warning + crash      -> Oodle re-compress (2.9.12 stream not decodable by the
                            game's static Oodle) or the write-mechanism is the bug.

Target the resource the game actually loads (the boot patch's Arabic UI):
  ACBF_FORGE=<...DataPC_boot_patch_01.forge> ACBF_UI_IDX=1244 \
      python build_identity_test.py --deploy   # (game CLOSED)
  ... --revert   # restore

Uses the pristine backup blob (_menu_proof_<forge>_<idx>.bin) written by
build_menu_proof.py, so the Arabic content is the true original (not our Hebrew).
"""
import importlib.util
import os
import sys
import struct
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")


def _load(n):
    p = os.path.join(TOOLS, n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
CFD = _load("acbf_cfd"); AF = _load("acbf_forge")

FORGE = os.environ.get("ACBF_FORGE",
                       r"C:\Games\Assassin's Creed Black Flag Resynced\DataPC_boot.forge")
UI_IDX = int(os.environ.get("ACBF_UI_IDX", "27724"))
_TAG = f"{os.path.splitext(os.path.basename(FORGE))[0]}_{UI_IDX}"
BACKUP = os.path.join(HERE, f"_ident_{_TAG}.json")
PRISTINE = os.path.join(HERE, f"_menu_proof_{_TAG}.bin")   # written by build_menu_proof deploy


def _size_field_off(info, idx):
    return info["toc"] + idx * AF.REC + 16


def cmd(deploy, revert):
    o = CFD._oodle()
    info = AF.parse(FORGE)
    r = info["recs"][UI_IDX]
    sf_off = _size_field_off(info, UI_IDX)

    if revert:
        if not os.path.isfile(BACKUP):
            print("no identity backup"); return 1
        bk = json.load(open(BACKUP))
        # restore the CURRENT-before-identity bytes + size (that was the Hebrew build,
        # or whatever was live). We snapshot it on deploy.
        orig = open(bk["blobfile"], "rb").read()
        with open(FORGE, "r+b") as f:
            f.seek(bk["res_off"]); f.write(orig)
            f.seek(bk["size_field_off"]); f.write(struct.pack("<I", bk["size"]))
        os.remove(BACKUP); os.remove(bk["blobfile"])
        print(f"identity reverted: restored {len(orig):,} B, size -> {bk['size']:,}")
        return 0

    if not os.path.isfile(PRISTINE):
        print(f"pristine blob not found: {PRISTINE}  (run build_menu_proof --deploy first)"); return 1
    blob = open(PRISTINE, "rb").read()
    orig_size = len(blob)

    # decode -> verbatim CFDs -> re-encode with OUR Oodle, keeping the resource the
    # EXACT original byte size (CFD1 topped up with a raw-zero pad block) so the
    # TOC size field stays UNCHANGED (no gap -> DirectStorage contiguity preserved).
    cfds, consumed = CFD.decode_resource(blob, o)
    if len(cfds) != 2 or consumed != len(blob):
        print(f"unexpected pristine structure: {len(cfds)} CFDs consumed {consumed}/{len(blob)}"); return 1
    # EXACT-SIZE NATIVE identity: CFD1 = the loc object grown with an incompressible,
    # marker-free pad so NATURAL block-splitting compresses to the EXACT original size
    # (native block count, invariant CFD0@10==@4+51 preserved, pad after the single
    # package). CFD0 = the 20-byte descriptor with @10 = CFD1 decoded len. Size UNCHANGED
    # -> forge stays fully contiguous (the gap broke boot); the object's real content is
    # byte-identical, only the Oodle bytes differ (proven format-compatible: lead 0x8C).
    cfd0_data, cinfo0 = cfds[0]
    cfd1_object, cinfo1 = bytes(cfds[1][0]), cfds[1][1]
    cfd0_probe = CFD.build_cfd(cfd0_data, cinfo0, o)                 # raw 20 B -> fixed 51 B
    target_cfd1 = orig_size - len(cfd0_probe)
    # keep_at4=True: @4 stays the REAL object size (CLEAN object — the game parses only
    # [51, @4] at boot, so no garbage there); the incompressible pad sits OUTSIDE @4 in
    # block2's tail. 3 native blocks (isolates whether the previous 4th raw block hung).
    cfd1_bytes, dec_len = CFD.build_cfd_object_to_size(cfd1_object, cinfo1, o, target_cfd1,
                                                       level=7, keep_at4=True)
    cfd0_ba = bytearray(cfd0_data); struct.pack_into("<I", cfd0_ba, 10, dec_len & 0xFFFFFFFF)
    cfd0_bytes = CFD.build_cfd(bytes(cfd0_ba), cinfo0, o)
    new_blob = cfd0_bytes + cfd1_bytes
    print(f"identity(exact,3blk,@4-clean): pristine {orig_size:,} B -> {len(new_blob):,} B "
          f"(size UNCHANGED; CFD1 {len(cfd1_bytes):,}B dec {dec_len:,})")
    rc, rconsumed = CFD.decode_resource(new_blob, o)
    L2 = len(cfd1_object)
    obj_ok = len(rc) == 2 and rc[1][0][:L2] == cfd1_object       # CLEAN object byte-identical
    nblk = struct.unpack_from("<i", new_blob, len(cfd0_bytes) + 15)[0] if len(rc) == 2 else -1
    print(f"  re-decode: {len(rc)} CFDs, consumed {rconsumed}/{len(new_blob)}, "
          f"object-identical={obj_ok}, CFD1 blocks={nblk}")
    if len(new_blob) != orig_size or not obj_ok:
        print("  !! exact-3blk identity failed sanity — aborting"); return 1

    if not deploy:
        print("  dry-run: nothing written. Use --deploy.")
        return 0

    # snapshot the CURRENT live bytes (Hebrew build) so --revert restores it
    with open(FORGE, "rb") as f:
        f.seek(r["offset"]); live = f.read(r["size"])
    blobfile = os.path.join(HERE, f"_ident_{_TAG}_live.bin")
    open(blobfile, "wb").write(live)
    json.dump({"res_off": r["offset"], "size": r["size"], "size_field_off": sf_off,
               "blobfile": blobfile, "idx": UI_IDX}, open(BACKUP, "w"))

    with open(FORGE, "r+b") as f:
        f.seek(r["offset"]); f.write(new_blob)
        f.seek(sf_off); f.write(struct.pack("<I", len(new_blob)))
    print(f"  IDENTITY DEPLOYED at 0x{r['offset']:x}: {len(new_blob):,} B, size {r['size']:,} -> {len(new_blob):,}")
    print("  launch: if Arabic renders -> encoder is the bug; if crash -> Oodle/write is the bug.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return cmd(a.deploy, a.revert)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
