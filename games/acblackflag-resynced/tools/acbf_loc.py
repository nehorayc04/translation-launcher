#!/usr/bin/env python3
"""
acbf_loc.py -- AC Black Flag Resynced (scimitar-v50) localized-string extractor.

CRACKED v50 loc record format (2026-07-10, verified on DataPC_boot_patch_01
chunk@0x8f9716f: "Roberts!", "[small effort", "Calm... little" decoded clean):

    [ lineID    u64 ]                      # cross-language key (8 bytes BEFORE tag)
    [ 0xFADE9F44 u32 ]                     # localized-string field tag (44 9F DE FA)
    [ u16 = 0x0001 ]
    [ u16          ]                       # small varying field
    [ u64 groupID  ]                       # conversation/group id
    [ u16 = 0x0000 ]
    [ charLen   u32 ]  <- tag+18
    [ UTF-16LE text, charLen code units ]  <- tag+22

(AC Shadows v42 used tag+17 / tag+21 — v50 inserts one extra field, so the text
offset shifts by +1 relative to v42.)

Records live inside Oodle-Kraken 0x57FBAA33 chunks. We walk chunks linearly
(the v50 TOC is a separate, still-being-cracked structure — not needed to READ
loc), decode each, and pull every FADE9F44 record.

  python acbf_loc.py scan    "<forge>"  [--out J]      # per-chunk record+script stats
  python acbf_loc.py extract "<forge>"  --out J [--script ar|en|all]
  python acbf_loc.py chunk   "<forge>" <fileoff-hex>   # dump records of one chunk
"""
import sys
import os
import struct
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acshadows", "tools"))
os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")

MAGIC = 0x57FBAA33
MAGIC_LE = struct.pack("<I", MAGIC)
HDR = 0x1F
TAG = struct.pack("<I", 0xFADE9F44)
CHARLEN_OFF = 18   # from tag start
TEXT_OFF = 22      # from tag start


def content_end(data):
    e = len(data)
    while e > 0 and data[e - 1] == 0:
        e -= 1
    return e


_CFD_MAGIC = 0x1004FA9957FBAA33


def decode_blob(blob, oodle):
    """A resource blob = one or more CompressedFileData (CFD) blocks. Decodes
    the PROPER multi-block CFD structure (magic+cinfo+blockCount + block-info
    TABLE + all compressed blocks), not a naive per-chunk walk (that only works
    for single-block CFDs and silently truncates multi-block loc resources)."""
    out = bytearray()
    off = 0
    n = len(blob)
    while off + 19 <= n and struct.unpack_from("<Q", blob, off)[0] == _CFD_MAGIC:
        cinfo_count = struct.unpack_from("<i", blob, off + 15)[0]
        if cinfo_count < 1 or cinfo_count > 200000:
            break
        bi = off + 19
        try:
            blocks = [struct.unpack_from("<ii", blob, bi + 8 * i) for i in range(cinfo_count)]
        except struct.error:
            break
        p = bi + cinfo_count * 8
        bad = False
        for uncomp, comp in blocks:
            p += 4                                  # adler
            if comp <= 0 or uncomp <= 0 or uncomp > 32 * 1024 * 1024 or p + comp > n:
                bad = True
                break
            chunk = blob[p:p + comp]
            p += comp
            try:
                out += chunk if comp == uncomp else oodle.decompress(chunk, uncomp)
            except Exception:
                bad = True
                break
        if bad:
            break
        off = p
    return bytes(out)


def _reader():
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acbf_forge.py")
    spec = importlib.util.spec_from_file_location("acbf_forge", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def cmd_toc_scan(forge, out, min_recs):
    """TOC-driven: enumerate every resource, decode, report loc-bearing ones."""
    from acs_oodle import Oodle
    o = Oodle()
    AF = _reader()
    info = AF.parse(forge)
    recs = info["recs"]
    rows = []
    tot = {"ar": 0, "en": 0, "he": 0, "other": 0}
    base = os.path.basename(forge)
    f = open(forge, "rb")
    for n, r in enumerate(recs):
        if n % 10000 == 0:
            print(f"  {base}: {n}/{len(recs)} probed, {len(rows)} loc-res, "
                  f"ar={tot['ar']:,} en={tot['en']:,}", flush=True)
            if out:
                json.dump({"probed": n, "rows": rows, "tot": tot},
                          open(out, "w", encoding="utf-8"), ensure_ascii=False)
        if r["size"] < 40 or r["size"] > 60_000_000:
            continue
        f.seek(r["offset"]); blob = f.read(r["size"])
        # quick reject: the tag must appear somewhere after decode; cheap pre-check
        # by decoding only if the resource is plausibly loc (decode first chunk)
        dec = decode_blob(blob, o)
        if TAG not in dec:
            continue
        recs_here = list(records_in(dec))
        if len(recs_here) < min_recs:
            continue
        cls = {"ar": 0, "en": 0, "he": 0, "other": 0}
        for _, _, txt in recs_here:
            c = classify(txt); cls[c] += 1; tot[c] += 1
        rows.append({"i": r["i"], "off": r["offset"], "size": r["size"],
                     "hash": r["hash"], "flags": r["flags"], "records": len(recs_here),
                     "cls": cls, "dominant": max(cls, key=cls.get),
                     "sample": recs_here[0][2][:40]})
    f.close()
    rows.sort(key=lambda x: -x["records"])
    print(f"\nDONE {base}: {len(rows)} loc resources  "
          f"totals ar={tot['ar']:,} en={tot['en']:,} he={tot['he']:,} other={tot['other']:,}")
    for r in rows[:50]:
        print(f"  idx {r['i']:>6} hash 0x{r['hash']:08x} recs={r['records']:>5} "
              f"dom={r['dominant']:<5} ar={r['cls']['ar']:>5} en={r['cls']['en']:>5}  {r['sample']!r}")
    if out:
        json.dump({"probed": len(recs), "rows": rows, "tot": tot},
                  open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  -> {out}")
    return 0


def cmd_toc_extract(forge, idx, out):
    from acs_oodle import Oodle
    o = Oodle()
    AF = _reader()
    info = AF.parse(forge)
    r = info["recs"][idx]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); blob = f.read(r["size"])
    dec = decode_blob(blob, o)
    merged = {}
    for lid, gid, txt in records_in(dec):
        merged[str(lid)] = txt
    json.dump(merged, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"resource idx {idx} hash 0x{r['hash']:08x}: {len(merged)} strings -> {out}")
    return 0


def iter_decoded_chunks(data, oodle, start=0x41a):
    """Yield (chunk_file_off, decoded_bytes) for every valid Kraken/stored chunk."""
    end = content_end(data)
    pos = start
    while pos + HDR <= end:
        if struct.unpack_from("<I", data, pos)[0] != MAGIC:
            nxt = data.find(MAGIC_LE, pos + 1, end)
            if nxt == -1:
                return
            pos = nxt
            continue
        uncomp = struct.unpack_from("<I", data, pos + 0x13)[0]
        comp = struct.unpack_from("<I", data, pos + 0x17)[0]
        payoff = pos + HDR
        if comp == 0 or comp > end - payoff or uncomp == 0 or uncomp > (1 << 26):
            nxt = data.find(MAGIC_LE, pos + 4, end)
            if nxt == -1:
                return
            pos = nxt
            continue
        payload = data[payoff:payoff + comp]
        try:
            dec = payload if comp == uncomp else oodle.decompress(payload, uncomp)
        except Exception:
            pos = payoff + comp
            continue
        yield pos, dec
        pos = payoff + comp


def records_in(dec):
    """Yield (lineID, groupID, text) for every FADE9F44 record in decoded bytes."""
    n = len(dec)
    pos = 0
    while True:
        t = dec.find(TAG, pos)
        if t < 0:
            return
        pos = t + 4
        if t < 8 or t + TEXT_OFF > n:
            continue
        try:
            line_id = struct.unpack_from("<Q", dec, t - 8)[0]
            group_id = struct.unpack_from("<Q", dec, t + 8)[0]
            clen = struct.unpack_from("<I", dec, t + CHARLEN_OFF)[0]
            if clen == 0 or clen > 40000 or t + TEXT_OFF + clen * 2 > n:
                continue
            txt = dec[t + TEXT_OFF: t + TEXT_OFF + clen * 2].decode("utf-16-le", "replace")
            # sanity: reject if the "text" is full of nulls/control (misparse)
            if txt.count("\x00") > len(txt) // 3:
                continue
            yield line_id, group_id, txt
        except Exception:
            continue


def classify(txt):
    ar = sum(1 for c in txt if 0x0600 <= ord(c) <= 0x06FF or 0xFB50 <= ord(c) <= 0xFEFF)
    he = sum(1 for c in txt if 0x0590 <= ord(c) <= 0x05FF)
    la = sum(1 for c in txt if c.isalpha() and ord(c) < 0x250)
    if ar > he and ar > la:
        return "ar"
    if he > la:
        return "he"
    if la:
        return "en"
    return "other"


def cmd_scan(forge, out):
    from acs_oodle import Oodle
    o = Oodle()
    data = open(forge, "rb").read()
    rows = []
    tot = {"ar": 0, "en": 0, "he": 0, "other": 0}
    for off, dec in iter_decoded_chunks(data, o):
        recs = list(records_in(dec))
        if not recs:
            continue
        cls = {"ar": 0, "en": 0, "he": 0, "other": 0}
        for _, _, txt in recs:
            cls[classify(txt)] += 1
            tot[classify(txt)] += 1
        dom = max(cls, key=cls.get)
        rows.append({"off": off, "records": len(recs), "cls": cls, "dominant": dom,
                     "sample": recs[0][2][:40]})
    rows.sort(key=lambda r: -r["records"])
    print(f"{os.path.basename(forge)}: {len(rows)} loc-bearing chunks  "
          f"totals ar={tot['ar']:,} en={tot['en']:,} he={tot['he']:,} other={tot['other']:,}")
    for r in rows[:40]:
        print(f"  chunk@0x{r['off']:<8x} recs={r['records']:>5} dom={r['dominant']:<5} "
              f"ar={r['cls']['ar']:>4} en={r['cls']['en']:>4}  {r['sample']!r}")
    if out:
        json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  -> {out}")
    return 0


def cmd_extract(forge, out, script):
    from acs_oodle import Oodle
    o = Oodle()
    data = open(forge, "rb").read()
    merged = {}
    for off, dec in iter_decoded_chunks(data, o):
        for line_id, group_id, txt in records_in(dec):
            if script != "all" and classify(txt) != script:
                continue
            merged[str(line_id)] = txt
    json.dump(merged, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{os.path.basename(forge)}: {len(merged):,} '{script}' strings -> {out}")
    return 0


def cmd_chunk(forge, fileoff):
    from acs_oodle import Oodle
    o = Oodle()
    data = open(forge, "rb").read()
    pos = int(fileoff, 0)
    uncomp = struct.unpack_from("<I", data, pos + 0x13)[0]
    comp = struct.unpack_from("<I", data, pos + 0x17)[0]
    dec = data[pos + HDR:pos + HDR + comp] if comp == uncomp else o.decompress(data[pos + HDR:pos + HDR + comp], uncomp)
    recs = list(records_in(dec))
    print(f"chunk@0x{pos:x} decoded={len(dec)} records={len(recs)}")
    for lid, gid, txt in recs[:40]:
        print(f"  lineID=0x{lid:x} group=0x{gid:x} [{classify(txt)}] {txt[:70]!r}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("forge"); s.add_argument("--out", default=None)
    e = sub.add_parser("extract"); e.add_argument("forge"); e.add_argument("--out", required=True)
    e.add_argument("--script", choices=["ar", "en", "he", "all"], default="all")
    c = sub.add_parser("chunk"); c.add_argument("forge"); c.add_argument("fileoff")
    ts = sub.add_parser("toc-scan"); ts.add_argument("forge"); ts.add_argument("--out", default=None)
    ts.add_argument("--min-recs", type=int, default=1)
    te = sub.add_parser("toc-extract"); te.add_argument("forge"); te.add_argument("idx", type=int); te.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "scan":
        return cmd_scan(a.forge, a.out)
    if a.cmd == "extract":
        return cmd_extract(a.forge, a.out, a.script)
    if a.cmd == "chunk":
        return cmd_chunk(a.forge, a.fileoff)
    if a.cmd == "toc-scan":
        return cmd_toc_scan(a.forge, a.out, a.min_recs)
    if a.cmd == "toc-extract":
        return cmd_toc_extract(a.forge, a.idx, a.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
