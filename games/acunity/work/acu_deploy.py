#!/usr/bin/env python3
r"""
acu_deploy.py — AC Unity (AnvilNext v27) forge WRITE-BACK via append-relocate.

Replaces ONE resource (by name) inside a `.forge` with a rebuilt blob, WITHOUT a
full 312 MB re-serialize and WITHOUT disturbing any other resource:

  * append the new blob at EOF  -> new_off
  * patch the resource's 20-byte record   (off -> new_off, size -> len(new))
  * patch the resource's 192-byte descriptor size field (+0x00 -> len(new))

Every AC-Unity forge resource is read by its OWN record (off + size); sizes are NOT
derived from neighbour offsets (verified: record field-4 == on-disk size for
1619/1620 resources, the lone diff being EOF padding). So relocating one resource to
EOF is safe — the vacated bytes become a harmless hole, and no neighbour over-reads.
Patch order is data -> descriptor -> record (record LAST), so an interrupted write
always leaves the ORIGINAL resource loadable.

Reversible: a full `<forge>.he_backup` is made before the first write; `--revert`
restores it. NEVER runs without a backup unless `--no-backup` is passed.

Usage:
  python acu_deploy.py <forge> <ResourceName> <new_blob.data>     # apply
  python acu_deploy.py <forge> --revert                           # restore backup
  python acu_deploy.py <forge> <ResourceName> --verify-only <blob> # dry check, no write
"""
import os
import sys
import shutil
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import acu_forge as F  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _descriptor_pos(fg, rec_index):
    """Absolute file offset of the 192-byte descriptor naming record `rec_index`."""
    name_tab = fg.rec_start + fg.count * 20
    region_len = fg._sorted_offs[0] - name_tab
    fg.f.seek(name_tab)
    region = fg.f.read(region_len)
    for k in range(region_len // F.DESC_STRIDE):
        base = k * F.DESC_STRIDE
        if struct.unpack_from("<I", region, base + F.DESC_INDEX_OFF)[0] == rec_index:
            return name_tab + base
    return None


def apply(forge_path, res_name, blob, backup=True):
    fg = F.Forge(forge_path)
    idx = fg.name_to_index.get(res_name)
    if idx is None:
        raise SystemExit(f"resource not found: {res_name}")
    off, fid, flags, usz = fg.recs[idx]
    rec_pos = fg.rec_start + idx * 20
    desc_pos = _descriptor_pos(fg, idx)
    fg.f.close()
    print(f"target [{idx}] {res_name}: old off=0x{off:x} size={usz:,}  rec@0x{rec_pos:x} desc@0x{desc_pos:x}")

    if backup:
        bak = forge_path + ".he_backup"
        if not os.path.exists(bak):
            print(f"backing up -> {bak} ({os.path.getsize(forge_path):,} B) ...")
            shutil.copy2(forge_path, bak)
        else:
            print(f"backup already present: {bak}")

    new_size = len(blob)
    with open(forge_path, "r+b") as fh:
        fh.seek(0, os.SEEK_END)
        new_off = fh.tell()
        fh.write(blob)                                             # 1) append data
        fh.flush()
        fh.seek(desc_pos + 0x00)                                   # 2) descriptor size copy
        fh.write(struct.pack("<I", new_size))
        fh.flush()
        fh.seek(rec_pos)                                           # 3) record LAST (off + size)
        fh.write(struct.pack("<QIII", new_off, fid, flags, new_size))
        fh.flush()
    print(f"appended {new_size:,} B at 0x{new_off:x}; patched record + descriptor.")
    return new_off, new_size


def apply_inplace(forge_path, res_name, blob, backup=True):
    """Overwrite a resource IN PLACE at its original offset (blob MUST be <= the resource's
    on-disk slot). No relocation, no hole, no record/descriptor change — the safest edit:
    the only bytes that change are inside the resource's own region. The resource is
    self-delimiting (CFD block counts), so the leftover tail bytes are ignored by the engine,
    and the size field (record + descriptor) is left as-is (contiguity and record-size both
    still resolve to the original slot; the CFD stops at the new, shorter end)."""
    fg = F.Forge(forge_path)
    idx = fg.name_to_index.get(res_name)
    if idx is None:
        raise SystemExit(f"resource not found: {res_name}")
    off, fid, flags, usz = fg.recs[idx]
    slot = fg.disk_size(idx)
    fg.f.close()
    if len(blob) > slot:
        raise SystemExit(f"blob {len(blob):,} > slot {slot:,} — cannot fit in place (use append-relocate)")
    print(f"target [{idx}] {res_name}: off=0x{off:x} slot={slot:,}  new blob={len(blob):,} "
          f"(fits, {slot-len(blob):,} B slack left as original tail)")
    if backup:
        bak = forge_path + ".he_backup"
        if not os.path.exists(bak):
            print(f"backing up -> {bak} ({os.path.getsize(forge_path):,} B) ...")
            shutil.copy2(forge_path, bak)
        else:
            print(f"backup already present: {bak}")
    with open(forge_path, "r+b") as fh:
        fh.seek(off)
        fh.write(blob)                     # overwrite only the first len(blob) bytes of the slot
        fh.flush()
    print(f"overwrote {len(blob):,} B at 0x{off:x} in place (record/descriptor untouched).")


def revert(forge_path):
    bak = forge_path + ".he_backup"
    if not os.path.exists(bak):
        raise SystemExit("no .he_backup to revert from")
    print(f"restoring {os.path.basename(forge_path)} from backup ...")
    shutil.copy2(bak, forge_path)
    print("reverted.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        raise SystemExit(2)
    forge = a[0]
    if "--revert" in a:
        revert(forge)
        raise SystemExit(0)
    res_name = a[1]
    blob_path = a[2] if len(a) > 2 and not a[2].startswith("--") else a[a.index("--verify-only") + 1]
    blob = open(blob_path, "rb").read()
    if "--verify-only" in a:
        fg = F.Forge(forge)
        idx = fg.name_to_index.get(res_name)
        print(f"[verify-only] would append {len(blob):,} B, relocate [{idx}] {res_name}. No write.")
        raise SystemExit(0)
    apply(forge, res_name, blob, backup="--no-backup" not in a)
