#!/usr/bin/env python3
"""
AC Black Flag Resynced (scimitar-v50) Hebrew MENU-PROOF.

Patches a handful of Arabic UI strings (resource idx 27724 in DataPC_boot.forge)
to Hebrew + a Latin marker, re-encodes the char-index LocalizationPackage, and
writes it back into boot.forge via APPEND-RELOCATE (append the new resource blob
at EOF, repoint that one TOC record's offset+size). Fully reversible.

The user has Text=ar-SA set already, so launching shows the Arabic UI — with our
patched strings now rendered in Hebrew (font already ships all 27 Hebrew glyphs).

  python build_menu_proof.py --deploy    # patch + write-back (game must be CLOSED)
  python build_menu_proof.py --revert     # restore original
  python build_menu_proof.py --dry-run    # build + validate offline, write nothing
"""
import importlib.util
import os
import sys
import struct
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, TOOLS)


def _load(n):
    p = os.path.join(TOOLS, n + ".py")
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
CFD = _load("acbf_cfd"); L = _load("acbf_loc"); AF = _load("acbf_forge"); LP = _load("acbf_locpkg")

FORGE = os.environ.get("ACBF_FORGE",
                       r"C:\Games\Assassin's Creed Black Flag Resynced\DataPC_boot.forge")
# The Arabic-UI LocalizationPackage. In the BASE forge it's record 27724, but a
# Ubisoft Connect update ships DataPC_boot_patch_01.forge which OVERRIDES the base
# (its record 1244 = Arabic UI), so the game loads the patch copy. Target whichever
# actually loads via env: ACBF_FORGE=<...patch_01.forge> ACBF_UI_IDX=1244.
UI_IDX = int(os.environ.get("ACBF_UI_IDX", "27724"))
# Per-(forge,idx) backup names so patching the patch never clobbers the base backup.
_TAG = f"{os.path.splitext(os.path.basename(FORGE))[0]}_{UI_IDX}"
BACKUP = os.path.join(HERE, f"_menu_proof_{_TAG}.json")

# stringID -> Hebrew replacement (ids verified present in the Arabic UI package)
PATCH = {
    12442499593651585653: "המשך",          # متابعة  Continue
    13763123497367102776: "יציאה",          # خروج    Exit
    13763533535708965377: "טעינה",          # تحميل   Load
    12435709294004715387: "עלילה",          # القصة   Story
    12432099737885992341: "שמירה",          # حفظ     Save
    12412719127741956672: "כללי ZZ-HEB-OK",  # عام     General + Latin mount marker
}


def _read_resource(forge, idx):
    info = AF.parse(forge)
    r = info["recs"][idx]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    return info, r, blob


def build_new_blob(blob, oodle):
    """Decode resource -> patch strings -> re-encode -> new blob, PRESERVING the
    original 2-CFD structure (a 20-byte metadata CFD0 whose u32@10 = CFD1's
    decoded size, + the loc CFD1).

    NO padding: the original resource's 2 CFDs fill its size EXACTLY (verified
    consumed==size, no trailer), so the game's loader walks CFDs until it has
    consumed `record.size` bytes. Zero-padding to the old size therefore made
    it try to parse a CFD out of the zeros -> hang at the first menu that loads
    this resource (past the intro warning). Instead we emit the new (smaller)
    2-CFD blob and the caller shrinks the TOC record's `size` field to match, so
    the resource again ends exactly where its CFDs end (like every native one).
    The offset is unchanged; the freed tail becomes a dead gap (harmless — every
    record is read by its own absolute TOC offset)."""
    cfds, _ = CFD.decode_resource(blob, oodle)
    if len(cfds) != 2:
        raise RuntimeError(f"expected 2 CFDs, got {len(cfds)}")
    cfd0 = bytearray(cfds[0][0]); cinfo0 = cfds[0][1]
    cfd1 = cfds[1][0]; cinfo1 = cfds[1][1]
    # the LocalizationPackage marker + payload live in CFD1
    m = cfd1.find(LP.MARKER)
    if m < 0:
        raise RuntimeError("marker not in CFD1")
    old_num = struct.unpack_from("<i", cfd1, m + 4)[0]
    strs = {}
    for pk in LP.find_packages(cfd1):
        strs.update(pk["strings"])
    id_text = list(strs.items())
    patched = 0
    for i, (sid, s) in enumerate(id_text):
        if sid in PATCH:
            id_text[i] = (sid, PATCH[sid]); patched += 1
    new_payload = LP.build_payload(id_text)
    new_cfd1 = bytearray(cfd1[:m + 4] + struct.pack("<i", len(new_payload)) + new_payload + cfd1[m + 8 + old_num:])
    # CFD1's Anvil object header @4 = the object's declared size = (total len - const).
    # We changed the payload length, so this MUST be re-derived or the game reads
    # `objsize` bytes out of a now-shorter object -> OOB -> "warning window + crash".
    obj_const = len(cfd1) - struct.unpack_from("<I", cfd1, 4)[0]   # 51 (invariant relation)
    struct.pack_into("<I", new_cfd1, 4, len(new_cfd1) - obj_const)
    new_cfd1 = bytes(new_cfd1)
    # update CFD0's embedded CFD1-size field (u32 LE @ +10)
    struct.pack_into("<I", cfd0, 10, len(new_cfd1))
    new_blob = CFD.build_cfd(bytes(cfd0), cinfo0, oodle) + CFD.build_cfd(new_cfd1, cinfo1, oodle)
    if len(new_blob) > len(blob):
        raise RuntimeError(f"new blob {len(new_blob)} exceeds original {len(blob)} — cannot in-place")
    return new_cfd1, new_blob, patched, len(strs)


BACKUP_BLOB = os.path.join(HERE, f"_menu_proof_{_TAG}.bin")


def _size_field_off(info, idx):
    """File offset of record `idx`'s u32 `size` field in the TOC:
    toc + idx*24 + 8(offset u64) + 4(ts) + 4(flags)."""
    return info["toc"] + idx * AF.REC + 16


def cmd(deploy, revert, dry):
    o = CFD._oodle()
    info = AF.parse(FORGE)
    r = info["recs"][UI_IDX]
    sf_off = _size_field_off(info, UI_IDX)

    if revert:
        if not (os.path.isfile(BACKUP) and os.path.isfile(BACKUP_BLOB)):
            print("no backup found"); return 1
        bk = json.load(open(BACKUP))
        orig = open(BACKUP_BLOB, "rb").read()
        with open(FORGE, "r+b") as f:
            f.seek(bk["res_off"]); f.write(orig)                        # restore original resource bytes
            f.seek(bk["size_field_off"]); f.write(struct.pack("<I", bk["orig_size"]))  # restore TOC size
        os.remove(BACKUP); os.remove(BACKUP_BLOB)
        print(f"reverted: resource {UI_IDX} restored at 0x{bk['res_off']:x} "
              f"({len(orig):,} B), TOC size -> {bk['orig_size']:,}")
        return 0

    # Always build from the PRISTINE original blob (the backup, if a mod is live).
    if os.path.isfile(BACKUP_BLOB):
        blob = open(BACKUP_BLOB, "rb").read()
        orig_size = len(blob)
    else:
        with open(FORGE, "rb") as f:
            f.seek(r["offset"]); blob = f.read(r["size"])
        orig_size = len(blob)

    new_cfd1, new_blob, patched, nstr = build_new_blob(blob, o)
    print(f"resource {UI_IDX}: {nstr} strings, patched {patched}/{len(PATCH)}")
    print(f"  new blob {len(new_blob):,} B  (original {orig_size:,} B; TOC size will shrink to match)")
    if len(new_blob) > orig_size:
        print("  !! new blob larger than original — cannot in-place; aborting"); return 1

    # OFFLINE VALIDATE: re-read our new blob back — must be EXACTLY 2 CFDs that
    # consume the whole blob (consumed==len), like every native resource.
    cfds2, consumed = CFD.decode_resource(new_blob, o)
    dec2 = b"".join(d for d, _ in cfds2)
    back = {}
    for pk in LP.find_packages(dec2):
        back.update(pk["strings"])
    okp = sum(1 for sid, heb in PATCH.items() if back.get(sid) == heb)
    print(f"  offline re-read: {len(cfds2)} CFDs, consumed {consumed}/{len(new_blob)}, "
          f"{len(back)} strings, {okp}/{len(PATCH)} Hebrew verified")
    if okp != len(PATCH) or len(cfds2) != 2 or consumed != len(new_blob):
        print("  !! validation failed — aborting"); return 1
    if dry or not deploy:
        print("  dry-run: nothing written. Use --deploy to write into boot.forge.")
        return 0

    with open(FORGE, "r+b") as f:
        if not os.path.isfile(BACKUP_BLOB):
            open(BACKUP_BLOB, "wb").write(blob)                          # backup pristine resource bytes
        json.dump({"res_off": r["offset"], "orig_size": orig_size,
                   "size_field_off": sf_off, "idx": UI_IDX}, open(BACKUP, "w"))
        f.seek(r["offset"]); f.write(new_blob)                           # overwrite in place (smaller)
        f.seek(sf_off); f.write(struct.pack("<I", len(new_blob)))        # shrink TOC size field
    print(f"  DEPLOYED at 0x{r['offset']:x}: {len(new_blob):,} B, TOC size {orig_size:,} -> {len(new_blob):,}")
    print(f"  backup -> {BACKUP_BLOB}  (revert with --revert)")
    print("  launch the game (Text=ar-SA already set); the menu strings should read Hebrew.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return cmd(a.deploy, a.revert, a.dry_run)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
