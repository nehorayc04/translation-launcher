#!/usr/bin/env python3
"""
mirage_deploy.py — write a rebuilt resource back into an AC Mirage v29 forge by
**append-relocate** (the proven AC Unity / 007 First Light pattern).

Why append-relocate and not a full re-pack: every resource is read through its OWN
20-byte record (`i64 offset, u64 id, i32 length_on_disk`) and the records are
offset-monotonic, so moving ONE resource to EOF leaves a harmless hole and no
neighbour over-reads. The header, the FileSet table and every other resource stay
byte-identical, so the engine still parses the file as the base it already loads —
and the new blob may be ANY size.

  1) append the new blob at EOF                  -> new_off
  2) patch that record's `offset`  (rec_pos + 0)
  3) patch that record's `length`  (rec_pos + 16)

A pristine `<forge>.he_backup` is made before the first write; `--revert` restores it.
The record fields are also journalled to `<forge>.he_journal.json` so a revert works
even if the backup is lost.

    python mirage_deploy.py <forge> apply   <resource_id> <blob.bin>   # relocate to EOF
    python mirage_deploy.py <forge> inplace <resource_id> <blob.bin>   # PREFERRED when it fits
    python mirage_deploy.py <forge> verify <resource_id>
    python mirage_deploy.py <forge> revert
"""
import argparse
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mirage_forge import Forge  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _entry(fg, res_id):
    m = [e for e in fg.entries if e.id == int(res_id)]
    if not m:
        raise SystemExit(f"resource id {res_id} not found")
    if len(m) > 1:
        print(f"[warn] {len(m)} entries share id {res_id}; using the first")
    return m[0]


def backup_path(forge):
    return forge + ".he_backup"


def journal_path(forge):
    return forge + ".he_journal.json"


def apply(forge, res_id, blob, make_backup=True):
    fg = Forge(forge)
    e = _entry(fg, res_id)
    fg.f.close()

    if make_backup and not os.path.exists(backup_path(forge)):
        print(f"backing up -> {os.path.basename(backup_path(forge))} "
              f"({os.path.getsize(forge)/1e6:.0f} MB) ...")
        shutil.copy2(forge, backup_path(forge))

    jp = journal_path(forge)
    jr = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {}
    jr.setdefault(str(e.id), {"rec_pos": e.rec_pos, "offset": e.offset, "size": e.size})

    with open(forge, "r+b") as fh:
        fh.seek(0, os.SEEK_END)
        new_off = fh.tell()
        fh.write(blob)                                        # 1) append
        fh.seek(e.rec_pos)
        fh.write(struct.pack("<q", new_off))                  # 2) offset
        fh.seek(e.rec_pos + 16)
        fh.write(struct.pack("<i", len(blob)))                # 3) length_on_disk
        fh.flush()
        os.fsync(fh.fileno())

    json.dump(jr, open(jp, "w", encoding="utf-8"), indent=1)
    print(f"appended {len(blob):,} B at 0x{new_off:x}  "
          f"(was 0x{e.offset:x} / {e.size:,} B); record @0x{e.rec_pos:x} patched.")
    return verify(forge, res_id, quiet=False)


def apply_inplace(forge, res_id, blob, make_backup=True):
    """Write the blob AT ITS ORIGINAL OFFSET, zero-padded to the original length.

    Preferred over append-relocate whenever the new blob is not larger. Anvil forges
    are streamed (DirectStorage) and AC Black Flag Resynced proved that a newer Anvil
    refuses a forge that is not 100% contiguous — a relocate leaves a hole at the old
    offset and puts the data past EOF. This shape moves NOTHING: the file size, every
    record, every offset and every length stay byte-identical, and only the bytes
    inside the resource's own slot change. The CFD chain self-terminates, so the
    zero padding after it is never parsed.
    """
    fg = Forge(forge)
    e = _entry(fg, res_id)
    fg.f.close()
    if len(blob) > e.size:
        raise SystemExit(f"blob {len(blob):,} > slot {e.size:,} — use `apply` instead")

    if make_backup and not os.path.exists(backup_path(forge)):
        print(f"backing up -> {os.path.basename(backup_path(forge))} "
              f"({os.path.getsize(forge)/1e6:.0f} MB) ...")
        shutil.copy2(forge, backup_path(forge))

    before = os.path.getsize(forge)
    with open(forge, "r+b") as fh:
        fh.seek(e.offset)
        fh.write(blob + b"\x00" * (e.size - len(blob)))
        fh.flush()
        os.fsync(fh.fileno())
    after = os.path.getsize(forge)
    print(f"in-place: {len(blob):,} B at 0x{e.offset:x} (+{e.size-len(blob):,} B zero pad) "
          f"into a {e.size:,} B slot; records untouched; "
          f"file {before:,} -> {after:,} {'(unchanged)' if before == after else '(CHANGED!)'}")
    return 0


def verify(forge, res_id, quiet=False):
    fg = Forge(forge)
    e = _entry(fg, res_id)
    bad = fg.validate()
    ok = e.offset + e.size <= fg.fsz
    if not quiet:
        print(f"verify: id={e.id} off=0x{e.offset:x} size={e.size:,} "
              f"in-bounds={ok}  (forge {fg.fsz:,} B)")
        print(f"        entries={len(fg.entries):,}  contiguity-violations={bad} "
              f"(1 expected after a relocate: the moved resource)")
    fg.f.close()
    return 0 if ok else 1


def revert(forge):
    bp = backup_path(forge)
    if os.path.exists(bp):
        print(f"restoring from {os.path.basename(bp)} ...")
        shutil.copy2(bp, forge)
        for p in (journal_path(forge),):
            if os.path.exists(p):
                os.remove(p)
        print("reverted (byte-identical).")
        return 0
    jp = journal_path(forge)
    if not os.path.exists(jp):
        raise SystemExit("no backup and no journal — nothing to revert")
    jr = json.load(open(jp, encoding="utf-8"))
    with open(forge, "r+b") as fh:
        for _rid, r in jr.items():
            fh.seek(r["rec_pos"])
            fh.write(struct.pack("<q", r["offset"]))
            fh.seek(r["rec_pos"] + 16)
            fh.write(struct.pack("<i", r["size"]))
    os.remove(jp)
    print(f"reverted {len(jr)} record(s) from the journal (appended bytes left as a tail).")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("cmd", choices=["apply", "inplace", "verify", "revert"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()

    if a.cmd == "revert":
        return revert(a.forge)
    if a.cmd == "verify":
        return verify(a.forge, a.args[0])
    blob = open(a.args[1], "rb").read()
    if a.cmd == "inplace":
        return apply_inplace(a.forge, a.args[0], blob, make_backup=not a.no_backup)
    return apply(a.forge, a.args[0], blob, make_backup=not a.no_backup)


if __name__ == "__main__":
    sys.exit(main())
