#!/usr/bin/env python3
"""
acs_loc_edit.py — locate & surgically edit a FADE9F44 localized line inside a
forge, IN PLACE (same on-disk size, delta-0 so the forge TOC never moves).
Reversible: backs up the original resource bytes to a sidecar before any write.

The decisive test the earlier analysis never ran: edit a dialogue line that is
in patch_01/boot but NOT overridden by patch_02, and see if it displays. The
FADE9F44 record tail is `[charLen u32][UTF-16LE text]` — we keep charLen and the
decoded size byte-identical by padding the Hebrew to the same code-unit count.

    locate "<forge>" <lineID...>   # find resource idx + size-fit dry run
    inject "<forge>" <lineID> <hebrew>   # backup + in-place overwrite (game CLOSED)
    injectfile "<forge>" <map.json>      # {lineID: hebrew} batch, one resource at a time
    revert "<forge>"                     # restore every .locbak_* sidecar
"""
import sys, os, struct, json, glob

TAG = struct.pack("<I", 0xFADE9F44)


def _tools():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F, acs_cfd as C
    return F, C


def _decode(forge, rec, o):
    import acs_cfd as C
    with open(forge, "rb") as f:
        f.seek(rec["offset"]); blob = f.read(rec["size"])
    cfds, _ = C.decode_resource(blob, o)
    return cfds


def _records(data):
    """yield (rec_start, line_id, clen, text_off) for every FADE9F44 record."""
    n = len(data); pos = 0
    while True:
        m = data.find(TAG, pos)
        if m < 0:
            break
        pos = m + 4
        if m < 8 or m + 21 > n:
            continue
        line_id = struct.unpack_from("<Q", data, m - 8)[0]
        clen = struct.unpack_from("<I", data, m + 17)[0]
        if clen <= 0 or clen > 60000 or m + 21 + clen * 2 > n:
            continue
        yield (m, line_id, clen, m + 21)


def _scan(forge, want_ids, o, max_size=15_000_000):
    """Find the resource(s) holding any of want_ids. Returns
    {index: {'cfds':..., 'si':largest_cfd_idx, 'hits':{lineID:(clen,text)}}}."""
    F, C = _tools()
    info = F.parse(forge); base = os.path.basename(forge)
    want = set(want_ids); found = {}
    for n, r in enumerate(info["recs"]):
        if n % 5000 == 0:
            print(f"  {base}: {n}/{info['count']} probed, {len(found)} resources hit", flush=True)
        if r["size"] < 64 or (max_size and r["size"] > max_size):
            continue
        try:
            cfds = _decode(forge, r, o)
        except Exception:
            continue
        data = b"".join(d for d, _ in cfds)
        if TAG not in data:
            continue
        hits = {}
        for (m, lid, clen, toff) in _records(data):
            if lid in want:
                hits[lid] = (clen, data[toff:toff + clen * 2].decode("utf-16-le", "replace"))
        if hits:
            si = max(range(len(cfds)), key=lambda i: len(cfds[i][0]))
            found[r["i"]] = {"rec": r, "cfds": cfds, "si": si, "hits": hits}
            want -= set(hits)
            if not want:
                break
    return found


def cmd_locate(forge, ids):
    F, C = _tools(); o = C._oodle()
    found = _scan(forge, ids, o)
    if not found:
        print("NOT FOUND in this forge"); return 1
    for idx, fr in found.items():
        # size-fit dry run: re-encode unchanged
        blob = b"".join(C.build_cfd(d, ci, o) for d, ci in fr["cfds"])
        orig = fr["rec"]["size"]
        allrec = list(_records(b"".join(d for d, _ in fr["cfds"])))
        print(f"\nresource idx {idx}  on-disk {orig}B  re-encode {len(blob)}B "
              f"fit={'Y' if len(blob)<=orig else 'N(+%d)'%(len(blob)-orig)}  "
              f"FADE9F44 records in resource: {len(allrec)}")
        for lid, (clen, txt) in fr["hits"].items():
            print(f"   lineID {lid}  charLen {clen}  EN={txt!r}")
    return 0


def _inject_into(data, edits):
    """edits: {lineID:(clen,hebrew)}. Replace UTF-16 padded to clen. Same size."""
    out = bytearray(data); applied = 0
    for (m, lid, clen, toff) in _records(data):
        if lid in edits:
            heb = edits[lid][1]
            padded = (heb + " " * clen)[:clen]
            rep = padded.encode("utf-16-le")
            assert len(rep) == clen * 2
            out[toff:toff + clen * 2] = rep
            applied += 1
    return bytes(out), applied


def _write_inplace(forge, r, cfds, new_datas, o):
    F, C = _tools()
    idx = r["i"]
    # rebuild EACH CFD from its own (possibly edited) decompressed data — never mix
    # CFDs (a resource is [file-table CFD][file-data CFD]; the strings live in one of
    # them and each CFD's record offsets are CFD-local, so edit per-CFD).
    new_cfds = [C.build_cfd(new_datas[i], ci, o) for i, (d, ci) in enumerate(cfds)]
    blob = b"".join(new_cfds)
    # SAFETY: re-decode and require byte-faithful structure (same #CFDs + same decomp
    # lengths). Makes it physically impossible to write a structurally-corrupt resource.
    try:
        back, _ = C.decode_resource(blob, o)
    except Exception as ex:
        print(f"  ABORT idx {idx}: re-decode failed ({ex})"); return False
    if len(back) != len(cfds) or any(len(back[i][0]) != len(cfds[i][0]) for i in range(len(cfds))):
        print(f"  ABORT idx {idx}: structural drift (refusing to write)"); return False
    if len(blob) > r["size"]:
        print(f"  ABORT idx {idx}: re-encoded {len(blob)} > original {r['size']}")
        return False
    blob = blob + b"\x00" * (r["size"] - len(blob))
    bak = f"{forge}.locbak_{idx}"
    if not os.path.exists(bak):
        with open(forge, "rb") as f:
            f.seek(r["offset"]); open(bak, "wb").write(f.read(r["size"]))
        print(f"  backup -> {os.path.basename(bak)} ({r['size']}B)")
    with open(forge, "r+b") as f:
        f.seek(r["offset"]); f.write(blob)
    print(f"  wrote idx {idx}: {len(blob)}B at 0x{r['offset']:x}")
    return True


def cmd_inject(forge, mapping):
    """mapping: {lineID(int): hebrew}."""
    F, C = _tools(); o = C._oodle()
    found = _scan(forge, mapping.keys(), o)
    if not found:
        print("NOT FOUND"); return 1
    ok = 0
    for idx, fr in found.items():
        cfds = fr["cfds"]
        edits = {lid: (None, mapping[lid]) for lid in fr["hits"]}  # _inject_into reads clen from data
        new_datas = []; applied = 0
        for (d, ci) in cfds:                       # edit each CFD on ITS OWN data
            nd, a = _inject_into(d, edits)
            new_datas.append(nd); applied += a
        if applied and _write_inplace(forge, fr["rec"], cfds, new_datas, o):
            for lid in fr["hits"]:
                print(f"    lineID {lid}: {fr['hits'][lid][1]!r} -> {mapping[lid]!r}")
            ok += applied
    print(f"\ninjected {ok} line(s)")
    return 0 if ok else 1


def cmd_revert(forge):
    F, _ = _tools()
    info = F.parse(forge); n = 0
    for bak in glob.glob(f"{forge}.locbak_*"):
        idx = int(bak.rsplit("_", 1)[1])
        r = info["recs"][idx]
        orig = open(bak, "rb").read()
        with open(forge, "r+b") as f:
            f.seek(r["offset"]); f.write(orig)
        print(f"reverted idx {idx} ({len(orig)}B)"); n += 1
    print(f"{n} resource(s) reverted" if n else "no .locbak_* backups found")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv
    if len(a) >= 3 and a[1] == "locate":
        sys.exit(cmd_locate(a[2], [int(x) for x in a[3:]]))
    if len(a) == 5 and a[1] == "inject":
        sys.exit(cmd_inject(a[2], {int(a[3]): a[4]}))
    if len(a) == 4 and a[1] == "injectfile":
        m = {int(k): v for k, v in json.load(open(a[3], encoding="utf-8")).items()}
        sys.exit(cmd_inject(a[2], m))
    if len(a) == 3 and a[1] == "revert":
        sys.exit(cmd_revert(a[2]))
    print(__doc__)
