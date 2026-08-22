#!/usr/bin/env python3
r"""
aor_deploy.py — write a rebuilt resource back into an AC Origins v28 forge by
**append-relocate** (the proven AC Unity v27 / AC Mirage v29 / 007 pattern).

Why append-relocate: every resource is read through its OWN 20-byte record
(`i64 offset, u64 id, i32 length_on_disk`) and the records are offset-monotonic,
so moving ONE resource to EOF leaves a harmless hole and no neighbour over-reads.
The header, the FileSet table and every other resource stay byte-identical, so the
engine still parses the file as the base it already loads — and the new blob may be
ANY size. That matters here: the rebuilt LocalizationPackage payload is ~2.4x the
shipped one (the game uses a multi-char fragment dict, our encoder is single-char),
so `inplace` will NOT fit and `apply` is the only route for text.

  1) append the new blob at EOF                  -> new_off
  2) patch that record's `offset`  (rec_pos + 0)
  3) patch that record's `length`  (rec_pos + 16)

⚠️ PREFETCH: several forges ship a sibling `<name>.prefetch` (a streaming hint
table). `DataPC_patch_01.forge` — the one that WINS for localization — has none,
which is one more reason to prefer it as the text target. `DataPC.forge` does have
one; `--check-prefetch` warns about it.

A pristine `<forge>.he_backup` is made before the first write; `--revert` restores
it. The record fields are ALSO journalled to `<forge>.he_journal.json` so a revert
works even if the backup is lost/deleted.

    python aor_deploy.py <forge> apply   <resource_id> <blob.bin>
    python aor_deploy.py <forge> inplace <resource_id> <blob.bin>   # only if it fits
    python aor_deploy.py <forge> verify  <resource_id>
    python aor_deploy.py <forge> revert
"""
import argparse
import json
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aor_forge import Forge  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _entry(fg, res_id):
    m = [e for e in fg.entries if e.id == int(res_id)]
    if not m:
        raise SystemExit(f"resource id {res_id} not found in {fg.path}")
    if len(m) > 1:
        print(f"[warn] {len(m)} entries share id {res_id}; using the first")
    return m[0]


def backup_path(forge):
    return forge + ".he_backup"


def journal_path(forge):
    return forge + ".he_journal.json"


def _warn_prefetch(forge):
    pf = os.path.splitext(forge)[0] + ".prefetch"
    if os.path.exists(pf):
        print(f"[note] sibling prefetch exists: {os.path.basename(pf)} "
              f"({os.path.getsize(pf):,} B) — relocating in THIS forge moves a "
              f"resource the prefetch table may still point at.")


def _ensure_backup(forge, make_backup):
    if make_backup and not os.path.exists(backup_path(forge)):
        sz = os.path.getsize(forge)
        print(f"backing up -> {os.path.basename(backup_path(forge))} "
              f"({sz/1e9:.2f} GB) ...")
        shutil.copy2(forge, backup_path(forge))


def apply(forge, res_id, blob, make_backup=True):
    fg = Forge(forge)
    e = _entry(fg, res_id)
    fg.close()

    _warn_prefetch(forge)
    _ensure_backup(forge, make_backup)

    jp = journal_path(forge)
    jr = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {}
    # remember the pristine EOF once, so a journal-only revert can truncate the
    # appended tail and restore the file BYTE-IDENTICALLY without the (multi-GB)
    # backup copy.
    jr.setdefault("_filesize", os.path.getsize(forge))
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
    print(f"  id={e.id}: appended {len(blob):,} B at 0x{new_off:x} "
          f"(was 0x{e.offset:x} / {e.size:,} B); record @0x{e.rec_pos:x} patched.")
    return 0


def apply_inplace(forge, res_id, blob, make_backup=True):
    """Write the blob AT ITS ORIGINAL OFFSET, zero-padded to the original length.
    Moves nothing — file size, records, offsets all byte-identical. The CFD chain
    self-terminates, so the zero padding after it is never parsed."""
    fg = Forge(forge)
    e = _entry(fg, res_id)
    fg.close()
    if len(blob) > e.size:
        raise SystemExit(f"blob {len(blob):,} > slot {e.size:,} — use `apply` instead")

    _ensure_backup(forge, make_backup)
    before = os.path.getsize(forge)
    with open(forge, "r+b") as fh:
        fh.seek(e.offset)
        fh.write(blob + b"\x00" * (e.size - len(blob)))
        fh.flush()
        os.fsync(fh.fileno())
    after = os.path.getsize(forge)
    print(f"  id={e.id}: in-place {len(blob):,} B at 0x{e.offset:x} "
          f"(+{e.size-len(blob):,} zero pad) into a {e.size:,} B slot; "
          f"file {before:,} -> {after:,} "
          f"{'(unchanged)' if before == after else '(CHANGED!)'}")
    return 0


def verify(forge, res_id=None, quiet=False):
    fg = Forge(forge)
    bad = fg.validate()
    rc = 0
    if res_id is not None:
        e = _entry(fg, res_id)
        ok = e.offset + e.size <= fg.fsz
        rc = 0 if ok else 1
        if not quiet:
            print(f"verify: id={e.id} off=0x{e.offset:x} size={e.size:,} in-bounds={ok}")
    if not quiet:
        print(f"        forge={fg.fsz:,} B  entries={len(fg.entries):,}  "
              f"contiguity-violations={bad} "
              f"(one per relocated resource is EXPECTED)")
    fg.close()
    return rc


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
    orig_size = jr.pop("_filesize", None)
    with open(forge, "r+b") as fh:
        for _rid, r in jr.items():
            fh.seek(r["rec_pos"])
            fh.write(struct.pack("<q", r["offset"]))
            fh.seek(r["rec_pos"] + 16)
            fh.write(struct.pack("<i", r["size"]))
        # drop the appended tail so the revert is byte-identical, not merely correct
        if orig_size is not None and os.path.getsize(forge) > orig_size:
            fh.truncate(orig_size)
        fh.flush()
        os.fsync(fh.fileno())
    os.remove(jp)
    tail = "" if orig_size is None else f", truncated back to {orig_size:,} B"
    print(f"reverted {len(jr)} record(s) from the journal{tail}.")
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
        return verify(a.forge, a.args[0] if a.args else None)
    blob = open(a.args[1], "rb").read()
    if a.cmd == "inplace":
        return apply_inplace(a.forge, a.args[0], blob, make_backup=not a.no_backup)
    return apply(a.forge, a.args[0], blob, make_backup=not a.no_backup)


if __name__ == "__main__":
    sys.exit(main())
