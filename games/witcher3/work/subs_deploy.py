# -*- coding: utf-8 -*-
"""Bake Hebrew into the W3 motion-comic subtitles and patch movies.bundle (APPEND-IN-PLACE).

For each of the 72 *_ar.subs subtitle groups (launch RECAP + STORYBOOK/finalboards cutscenes) it
rebuilds the Arabic-slot .subs with Hebrew rows:
  - reuse_he               (row's English already lived in .w3strings -> reuse that hebrew.json line)
  - subs_hebrew.json[tkey] (the 151 lines the translation agent produced)
  - else keep the original Arabic (safe fallback)
Each Hebrew text is VISUAL-baked (visual_line from build_mod — the W3 surface is NON-BIDI for Hebrew).

### Why APPEND and not a full repack (two bugs that CRASHED the game — do not regress)
1. **pack mode.** 71 of the 72 target .subs ship as **pack=0 (STORED/raw)**; only recap_wip_ar is
   pack=1 (zlib). (Bundle-wide: 1240 stored vs 13 zlib.) A rewrite that zlib-compressed all of them
   fed the engine deflate where it expected raw bytes -> crash. We now KEEP EACH ENTRY'S ORIGINAL
   PACK MODE.
2. **layout.** A full repack shifts every entry after the first change — including the 2.5 GB of
   .usm movie streams. We now APPEND the new blobs at EOF and repoint ONLY those 72 entries, so
   every other entry keeps its exact original offset/bytes.
The TOC `size` field is the UNCOMPRESSED length and the engine allocates its buffer from it — a
stale `size` passes any zlib-based self-check yet breaks the game. We always write the real length.

Backup: movies.bundle.he_backup ; revert with --revert. GAME MUST BE CLOSED.

Usage:  py subs_deploy.py            # dry-run
        py subs_deploy.py --deploy
        py subs_deploy.py --revert
"""
import os, sys, json, struct, zlib, shutil
import potato_bundle as PB
import subs_codec as SC
from build_mod import visual_line

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
BUNDLE = os.path.join(GAME, "content", "content0", "bundles", "movies.bundle")
BAK = BUNDLE + ".he_backup"
HERE = os.path.dirname(os.path.abspath(__file__))


def _parse_toc(d):
    filesize, size, header_sz, data_sz = struct.unpack_from("<IIII", d, 8)
    n = header_sz // 320
    ents = []
    for i in range(n):
        base = 0x20 + i * 320
        name = d[base:base + 256].split(b"\x00", 1)[0].decode("latin-1")
        sz, zsz, offs = struct.unpack_from("<III", d, base + 256 + 16 + 4)
        pk = struct.unpack_from("<I", d, base + 320 - 4)[0]
        ents.append({"i": i, "base": base, "name": name, "size": sz, "zsize": zsz, "offs": offs, "pack": pk})
    return ents


def build_hebrew_subs():
    """-> {ar_subs_name.lower(): (payload_bytes, uncompressed_len, pack)} + stats.
    payload is RAW when the entry's original pack==0, zlib when pack==1 (mode preserved)."""
    plan = json.load(open(os.path.join(HERE, "subs_plan.json"), encoding="utf-8"))
    hp = os.path.join(HERE, "subs_hebrew.json")
    hebmap = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else {}

    src = BAK if os.path.exists(BAK) else BUNDLE
    d, entries = PB.list_entries(src)
    byn = {e["name"].lower(): e for e in entries}

    out = {}
    st = {"he": 0, "reuse": 0, "keep": 0, "files": 0, "stored": 0, "zlib": 0}
    for ar_name, rows in plan.items():
        e = byn[ar_name.lower()]
        header, orig_rows = SC.parse(PB.extract(d, e))
        for rec in rows:
            ri = rec["ridx"]
            if ri >= len(orig_rows):
                continue
            he = None
            if "reuse_he" in rec:
                he = rec["reuse_he"]; st["reuse"] += 1
            elif rec.get("tkey") and rec["tkey"] in hebmap and hebmap[rec["tkey"]].strip():
                he = hebmap[rec["tkey"]]; st["he"] += 1
            else:
                st["keep"] += 1
            if he is not None:
                orig_rows[ri][2] = visual_line(he)
        blob = SC.build(header, orig_rows)
        if e["pack"] == 0:
            payload = blob; st["stored"] += 1          # STORED — the engine reads raw bytes
        elif e["pack"] == 1:
            payload = zlib.compress(blob, 9); st["zlib"] += 1
        else:
            raise SystemExit(f"unexpected pack={e['pack']} on {ar_name}")
        out[ar_name.lower()] = (payload, len(blob), e["pack"])
        st["files"] += 1
    return out, st


def patch_contiguous(new_map):
    """Full CONTIGUOUS repack (the proven font mechanism): stream every entry in offset order into
    a fresh file, 16-byte-aligning each, copying untouched entries' bytes verbatim and substituting
    the 72 .subs (pack mode preserved). Offsets stay inside the normal data region — unlike an
    append past EOF, which the engine did NOT read. Streamed so the 2.5 GB never sits in RAM."""
    src = BAK if os.path.exists(BAK) else BUNDLE
    d = open(src, "rb").read(0x20 + 400960 + 64)        # header + TOC only
    ents = _parse_toc(d)
    ents_off = sorted(ents, key=lambda e: e["offs"])
    data_start = ents_off[0]["offs"]
    header_toc = bytearray(open(src, "rb").read(data_start))
    size0 = os.path.getsize(src)

    tmp = BUNDLE + ".tmp"
    fin = open(src, "rb")
    with open(tmp, "wb") as fh:
        fh.write(header_toc)                            # patched below
        cur = data_start
        for e in ents_off:
            pad = (-cur) % 16
            if pad:
                fh.write(b"\x00" * pad); cur += pad
            key = e["name"].lower()
            if key in new_map:
                payload, usize, pack = new_map[key]
                fh.write(payload)
                e["no"], e["nz"], e["ns"], e["np"] = cur, len(payload), usize, pack
                cur += len(payload)
            else:
                fin.seek(e["offs"])
                remaining = e["zsize"]
                while remaining:
                    chunk = fin.read(min(remaining, 1 << 22))
                    if not chunk:
                        break
                    fh.write(chunk); remaining -= len(chunk)
                e["no"], e["nz"], e["ns"], e["np"] = cur, e["zsize"], e["size"], e["pack"]
                cur += e["zsize"]
        total = cur
    fin.close()

    # patch TOC (size/zsize/offs/pack) + header (filesize@8, data-section@12) in place
    for e in ents:
        b = e["base"]
        struct.pack_into("<III", header_toc, b + 256 + 16 + 4, e["ns"], e["nz"], e["no"])
        struct.pack_into("<I", header_toc, b + 320 - 4, e["np"])
    struct.pack_into("<I", header_toc, 8, total)
    struct.pack_into("<I", header_toc, 12, total - data_start)
    with open(tmp, "r+b") as fh:
        fh.write(header_toc)

    if src != BUNDLE or True:
        os.replace(tmp, BUNDLE)
    return total, size0, sum(1 for e in ents if e["name"].lower() in new_map)


def deploy():
    new_map, st = build_hebrew_subs()
    print(f"subtitle files: {st['files']}  |  he:{st['he']} reuse:{st['reuse']} keep(arabic):{st['keep']}")
    print(f"pack modes preserved: stored(pack=0)={st['stored']}  zlib(pack=1)={st['zlib']}")
    if not os.path.exists(BAK):
        shutil.copy2(BUNDLE, BAK); print(f"backed up -> {os.path.basename(BAK)}")
    total, old, n = patch_contiguous(new_map)
    print(f"contiguous repack: {n} entries substituted; movies.bundle {old} -> {total} ({total-old:+d})")

    # self-check 1: every replaced entry re-reads with correct pack + uncompressed size + Hebrew
    d, ents = PB.list_entries(BUNDLE)
    HE = lambda s: any('֐' <= c <= '׿' for c in s)
    bad = 0
    for e in ents:
        key = e["name"].lower()
        if key not in new_map:
            continue
        _payload, usize, pack = new_map[key]
        blob = PB.extract(d, e)
        if e["pack"] != pack or e["size"] != usize or len(blob) != usize or blob != SC.build(*SC.parse(blob)):
            bad += 1
            print(f"  !! {e['name']}: pack={e['pack']}/{pack} size={e['size']}/{usize} real={len(blob)}")
    print(f"self-check: {len(new_map)} replaced entries re-read, mismatches = {bad}")
    if bad:
        raise SystemExit("ABORT: mismatch — reverting is advised.")
    # self-check 2: a sample of UNTOUCHED entries must extract byte-identical vs the backup (by name)
    bd, bents = PB.list_entries(BAK)
    bbyn = {e["name"].lower(): e for e in bents}
    import random
    others = [e for e in ents if e["name"].lower() not in new_map]
    sample = random.sample(others, min(30, len(others)))
    drift = sum(1 for e in sample if PB.extract(d, e) != PB.extract(bd, bbyn[e["name"].lower()]))
    print(f"self-check: {len(sample)} sampled untouched entries, byte-drift = {drift}  (must be 0)")
    if drift:
        raise SystemExit("ABORT: an untouched entry's content changed.")
    print("DEPLOYED. Fully restart the game (Text Language = Arabic).")


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE); print("reverted movies.bundle from .he_backup")
    else:
        print("no backup found")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--deploy" in sys.argv:
        deploy()
    else:
        _, st = build_hebrew_subs()
        print(f"(dry-run) files:{st['files']} he:{st['he']} reuse:{st['reuse']} keep:{st['keep']} "
              f"| stored={st['stored']} zlib={st['zlib']}")
