#!/usr/bin/env python3
"""
acs_deploy.py — the AC Shadows (scimitar v42) loc deploy engine.

PHASE 0 = `--identity`: re-encode every loc resource with OUR Oodle but with the
content BYTE-UNCHANGED, write it back IN PLACE (same record size, natural blob +
trailing zeros), and verify offline. This is the exact A/B control for the June
crash: same resource set, same write path, content held constant.
  - boots  => our Oodle + CFD encode + in-place pad are all fine on v42
              => the June crash was CONTENT, not structure/validation.
  - crashes => the pad or our Oodle IS the problem => go to the repack path.

v42 layout (VERIFIED on DataPC_boot_patch_01.forge, 11.17 GB, 46,564 records):
    [header 0..0x41a] [index hdr @0x41a] [TOC record array @0x462 .. 0x1111c2]
    [ptr block @0x1111c2: u64 = data_end] [resource data 0x1112b3 .. data_end]
    [name/path table (REAL DATA, not padding) .. EOF]
  => the TOC sits at the FRONT (the OPPOSITE of Black Flag v50, where it trails the
     data). An in-place same-size write therefore touches nothing but the blob.

v42 resource structure (VERIFIED — NOT the v50 `CFD0@10 == @4+51` rule):
    CFD0 = [u16 fileCount][fileCount x 18B entry {u32 fileID, u32 flags, u32 size, u32, u16}]
    CFD1 = the file payloads concatenated; each = [u32 classHash][u32 payloadSize]
           [u32 nameLen][name...][payload]
    => CFD0's per-file `size` == 13 + nameLen + payloadSize. An edit that keeps the
       UTF-16 charLen keeps every length field valid; nothing to re-derive.

    python acs_deploy.py --identity   # re-encode, content unchanged (Phase 0 gate)
    python acs_deploy.py --verify     # offline: forge vs pristine sidecars
    python acs_deploy.py --revert     # restore every .locbak_* sidecar
"""
import argparse
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_forge as F  # noqa: E402
import acs_cfd as C  # noqa: E402

FORGE = os.environ.get(
    "ACS_FORGE", r"C:\Games\Assassin's Creed Shadows\DataPC_boot_patch_01.forge")
# Oodle levels tried in order until the blob fits the original record size.
LEVELS = (4, 6, 7, 8, 9)


def loc_indices(forge=FORGE):
    """The loc resources — pinned by the pristine sidecars written on first touch."""
    return sorted(int(p.rsplit("_", 1)[1]) for p in glob.glob(forge + ".locbak_*"))


def read_rec(forge, rec):
    with open(forge, "rb") as f:
        f.seek(rec["offset"])
        return f.read(rec["size"])


def pristine(forge, idx, rec):
    """The vanilla blob: the sidecar if we ever wrote this record, else the forge."""
    bak = f"{forge}.locbak_{idx}"
    if os.path.isfile(bak):
        with open(bak, "rb") as f:
            return f.read()
    return read_rec(forge, rec)


def natural_blob(cfds, oodle, budget):
    """Re-encode CFDs naturally (no buffer pad, native block count). Try harder
    Oodle levels until the blob fits `budget`. Returns (blob, level) or (None, None)."""
    for lv in LEVELS:
        blob = b"".join(C.build_cfd(d, ci, oodle, level=lv) for d, ci in cfds)
        if len(blob) <= budget:
            return blob, lv
    return None, None


def write_inplace(forge, rec, blob):
    """Same-size write: natural blob + trailing zeros to the original record size.
    Record offset/size never change => forge stays fully contiguous (rule 2)."""
    assert len(blob) <= rec["size"]
    padded = blob + b"\x00" * (rec["size"] - len(blob))
    with open(forge, "r+b") as f:
        f.seek(rec["offset"])
        f.write(padded)


def backup(forge, idx, rec, blob):
    bak = f"{forge}.locbak_{idx}"
    if not os.path.isfile(bak):
        with open(bak, "wb") as f:
            f.write(blob)


def cmd_identity(forge, limit=None):
    info = F.parse(forge)
    recs = info["recs"]
    good, tot = F.invariant(recs)
    if good != tot:
        print(f"ABORT: forge is not contiguous ({good}/{tot}) — refusing to touch it")
        return 1
    o = C._oodle()
    idxs = loc_indices(forge)
    if limit:
        idxs = idxs[:limit]
    print(f"forge  : {os.path.basename(forge)}  v{info['version']}  "
          f"{info['count']:,} records  contiguity {good}/{tot} OK")
    print(f"oodle  : {getattr(o, 'path', '?')}")
    print(f"targets: {len(idxs)} loc resources (identity — content UNCHANGED)\n")

    stats = {"ok": 0, "skip_nofit": 0, "fail": 0, "bytes_saved": 0}
    levels_used = {}
    nofit = []
    for n, i in enumerate(idxs):
        if n % 100 == 0:
            print(f"  {n}/{len(idxs)} ...", flush=True)
        rec = recs[i]
        orig = pristine(forge, i, rec)
        try:
            cfds, consumed = C.decode_resource(orig, o)
        except Exception as ex:
            print(f"  idx {i}: decode failed ({ex}) — skipped")
            stats["fail"] += 1
            continue
        if not cfds:
            continue
        blob, lv = natural_blob(cfds, o, rec["size"])
        if blob is None:
            stats["skip_nofit"] += 1
            nofit.append(i)
            continue
        # SAFETY: the re-encoded blob must decode back to byte-identical CFD data.
        back, _ = C.decode_resource(blob, o)
        if len(back) != len(cfds) or any(back[k][0] != cfds[k][0] for k in range(len(cfds))):
            print(f"  idx {i}: re-decode MISMATCH — refusing to write")
            stats["fail"] += 1
            continue
        backup(forge, i, rec, orig)
        write_inplace(forge, rec, blob)
        levels_used[lv] = levels_used.get(lv, 0) + 1
        stats["bytes_saved"] += rec["size"] - len(blob)
        stats["ok"] += 1

    print(f"\nwritten : {stats['ok']}/{len(idxs)}  (levels used: "
          f"{', '.join(f'L{k}x{v}' for k, v in sorted(levels_used.items()))})")
    print(f"no-fit  : {stats['skip_nofit']} left VANILLA {nofit[:12]}")
    print(f"failed  : {stats['fail']}")
    print(f"zero-pad: {stats['bytes_saved']:,} B total across written records")
    return 0 if stats["fail"] == 0 else 1


def cmd_verify(forge):
    """Offline proof: every touched record still decodes to its pristine content,
    the forge is contiguous, and the file size is unchanged."""
    info = F.parse(forge)
    recs = info["recs"]
    o = C._oodle()
    good, tot = F.invariant(recs)
    idxs = loc_indices(forge)
    same_bytes = decode_ok = decode_bad = 0
    for i in idxs:
        rec = recs[i]
        cur = read_rec(forge, rec)
        orig = pristine(forge, i, rec)
        if cur == orig:
            same_bytes += 1
            continue
        try:
            a, _ = C.decode_resource(orig, o)
            b, _ = C.decode_resource(cur, o)
            ok = len(a) == len(b) and all(a[k][0] == b[k][0] for k in range(len(a)))
        except Exception:
            ok = False
        decode_ok += ok
        decode_bad += (not ok)
    print(f"forge      : {os.path.basename(forge)}  size {os.path.getsize(forge):,}")
    print(f"contiguity : {good}/{tot} {'OK' if good == tot else '*** GAP — WILL BLACK-SCREEN ***'}")
    print(f"loc records: {len(idxs)}")
    print(f"  vanilla bytes      : {same_bytes}")
    print(f"  re-encoded, content IDENTICAL: {decode_ok}")
    print(f"  re-encoded, content DIFFERS  : {decode_bad}  "
          f"{'<-- BAD' if decode_bad else '(none)'}")
    return 0 if (good == tot and decode_bad == 0) else 1


def cmd_revert(forge):
    info = F.parse(forge)
    recs = info["recs"]
    n = 0
    for bak in glob.glob(forge + ".locbak_*"):
        i = int(bak.rsplit("_", 1)[1])
        rec = recs[i]
        with open(bak, "rb") as f:
            orig = f.read()
        if len(orig) != rec["size"]:
            print(f"  idx {i}: sidecar {len(orig)} != record {rec['size']} — SKIPPED")
            continue
        with open(forge, "r+b") as f:
            f.seek(rec["offset"])
            f.write(orig)
        n += 1
    print(f"reverted {n} resource(s) to pristine")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity", action="store_true", help="Phase 0: re-encode, content unchanged")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--forge", default=FORGE)
    a = ap.parse_args()
    if a.revert:
        return cmd_revert(a.forge)
    if a.verify:
        return cmd_verify(a.forge)
    if a.identity:
        return cmd_identity(a.forge, a.limit)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
