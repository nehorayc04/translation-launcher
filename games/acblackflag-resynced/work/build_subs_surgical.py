#!/usr/bin/env python3
"""
SURGICAL subtitle edit — the smallest possible change to the subtitle package.

Everything learned so far, by isolation:
  * shipping the subtitle record with its payload UNTOUCHED  -> game boots
  * re-encoding that payload from parsed text (even with the SAME text) -> black screen
    (the engine spins forever: CPU pegged, memory frozen, zero disk I/O)
  * the same re-encoder works fine on the UI package
So the layout math is right (a rebuild reusing the original fragment table and code bytes
is byte-identical) but something about a full re-encode of THIS package is rejected.

This build therefore changes as little as possible:
  * KEEP the original fragment table, appending leaves only for characters it lacks
  * KEEP the original code bytes verbatim for the 3 multi-line dialogue records
  * re-encode ONLY the single-line rows, with the ladder text
If this boots, the rejection is caused by re-encoding the dialogue records; if it black-
screens, even a minimal single-line edit is refused and the cause lies elsewhere.

    python work/build_subs_surgical.py --deploy
"""
import argparse
import importlib.util
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
INJ = os.path.join(HERE, "refmods", "injector", "oo2core_9_win64.dll")
os.environ["ACS_OODLE_DLL"] = INJ


def _load(n):
    p = os.path.join(TOOLS, n + ".py"); s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


AF = _load("acbf_forge"); CFD = _load("acbf_cfd"); LP = _load("acbf_locpkg")
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))
from acs_oodle import Oodle

GAME = os.environ.get("ACBF_GAME", r"C:\Games\Assassin's Creed Black Flag Resynced")
BOOT = os.path.join(GAME, "DataPC_boot.forge")
UA = os.path.join(HERE, "refmods", "ua", "DataPC_boot_patch_02.forge")
HEATLAS = os.path.join(HERE, "heatlas")
OUT = os.path.join(HERE, "refmods", "he", "DataPC_boot_patch_02.forge")

SUBS_FILEID = 0x668047C6
UI_FILEID = 0x668047C5
ATLAS_FILEIDS = [0x88C902B3, 0x88C902B5, 0x88C902B1]

NROWS = int(os.environ.get("ACBF_N_ROWS", "999999"))

CARRIER = {chr(int(k, 16)): chr(int(v, 16))
           for k, v in json.load(open(os.path.join(HERE, "carrier_map.json"))).items()}


def enc_carrier(t):
    return "".join(CARRIER.get(c, c) for c in t)


def vis(t):
    out, run = [], []
    for ch in t:
        if "\u05d0" <= ch <= "\u05ea" or ch == " ":
            run.append(ch)
        else:
            if run:
                out.append("".join(run)[::-1]); run = []
            out.append(ch)
    if run:
        out.append("".join(run)[::-1])
    return "".join(out)


HEB = "שלום עברית"


def variant(i):
    m = i % 3
    if m == 0:
        return "ZZ0 " + enc_carrier(HEB)
    if m == 1:
        return "ZZ1 " + enc_carrier(vis(HEB))
    return 'ZZ2 ' + enc_carrier('עברית') + ' "x" (y) 12.5% ABC'


def build_cfd_raw(data, cinfo):
    BLOCK = CFD.BLOCK
    nb = max(1, (len(data) + BLOCK - 1) // BLOCK)
    bi = bytearray(); cd = bytearray()
    for i in range(nb):
        raw = data[i * BLOCK:(i + 1) * BLOCK]
        bi += struct.pack("<ii", len(raw), len(raw))
        cd += struct.pack("<I", CFD.adler(raw)) + raw
    return struct.pack("<Q", CFD.MAGIC) + cinfo + struct.pack("<i", nb) + bytes(bi) + bytes(cd)


def surgical(buf, replace_single):
    """Rebuild the payload keeping the original fragment table and the original code bytes
    of every multi-line record; only single-line rows are re-encoded."""
    max_index, frag_count = struct.unpack_from(">HH", buf, 0)
    frags = [struct.unpack_from(">HH", buf, 4 + i * 4) for i in range(frag_count)]
    p = 4 + frag_count * 4
    rec_count = struct.unpack_from(">H", buf, p)[0]; p += 2
    raw = []
    for _ in range(rec_count):
        sid = struct.unpack_from(">Q", buf, p)[0]
        raw.append((sid, struct.unpack_from(">I", buf, p + 8)[0],
                    struct.unpack_from(">I", buf, p + 12)[0])); p += 16

    # leaf index for a character, appending to the ORIGINAL table when missing
    leaf = {}
    for i, (A, B) in enumerate(frags):
        if B == 0 and i:
            leaf.setdefault(chr(A), i)

    def frag_of(ch):
        if ch not in leaf:
            frags.append((ord(ch), 0)); leaf[ch] = len(frags) - 1
        return leaf[ch]

    def encode(t):
        out = bytearray()
        for ch in t:
            b = frag_of(ch) - 1
            if b < max_index:
                out.append(b)
            else:
                val = b + max_index * 255
                hi, lo = val >> 8, val & 0xFF
                if max_index <= hi <= 254:
                    out.append(hi); out.append(lo)
                else:
                    out.append(255); out += struct.pack(">h", b)
        return bytes(out)

    recs = []
    n_single = n_multi = 0
    for sid, code_off, aux_off in raw:
        cnt = struct.unpack_from(">H", buf, aux_off)[0]
        first = struct.unpack_from(">H", buf, aux_off + 2)[0]
        pairs = [struct.unpack_from(">HH", buf, aux_off + 4 + i * 4) for i in range(cnt)]
        ends = [first] + [pr[1] for pr in pairs]
        aux = [pr[0] for pr in pairs]
        segs, prev = [], 0
        for e in ends:
            segs.append(bytes(buf[code_off + prev:code_off + e])); prev = e
        # ACBF_N_ROWS caps how many single-line rows are edited (default: all).
        # N=1 is the true minimum: the payload grows by a handful of bytes, so if THAT is
        # still rejected the cause is not the encoding but something outside the package.
        if cnt == 0 and replace_single and n_single < NROWS:
            segs = [encode(variant(n_single))]; n_single += 1
        else:
            n_multi += 1
        recs.append((sid, segs, aux))

    aux_start = 4 + len(frags) * 4 + 2 + len(recs) * 16
    sizes = [4 + 4 * (len(s) - 1) for _, s, _ in recs]
    code_start = aux_start + sum(sizes)
    out = bytearray()
    out += struct.pack(">HH", max_index, len(frags))
    for A, B in frags:
        out += struct.pack(">HH", A, B)
    out += struct.pack(">H", len(recs))
    rb, ab, cb = bytearray(), bytearray(), bytearray()
    ao, co = aux_start, code_start
    for (sid, segs, aux), sz in zip(recs, sizes):
        rb += struct.pack(">QII", sid, co, ao)
        cum = len(segs[0]); ab += struct.pack(">HH", len(segs) - 1, cum); cb += segs[0]
        for i, s in enumerate(segs[1:]):
            cum += len(s)
            ab += struct.pack(">HH", aux[i], cum); cb += s
        co += cum; ao += sz
    out += rb + ab + cb
    print(f"  surgical: frags {frag_count} -> {len(frags)} (+{len(frags)-frag_count} leaves), "
          f"single rows re-encoded={n_single}, multi records kept verbatim={n_multi}, "
          f"payload {len(buf):,} -> {len(out):,}")
    return bytes(out)


def byte_poke(buf):
    """ZERO-SIZE, ZERO-OFFSET edit: flip ONE code byte in the first single-line row so a
    single CHARACTER changes to another character already present in the fragment table.
    Nothing moves — same payload length, same fragment table, same codeOffs, same aux.
    If even this is rejected the package content is validated (hash); if it loads, only
    OFFSETS matter and something outside the package indexes into it."""
    out = bytearray(buf)
    max_index, frag_count = struct.unpack_from(">HH", buf, 0)
    p = 4 + frag_count * 4
    rec_count = struct.unpack_from(">H", buf, p)[0]; p += 2
    for i in range(rec_count):
        sid = struct.unpack_from(">Q", buf, p + i * 16)[0]
        co = struct.unpack_from(">I", buf, p + i * 16 + 8)[0]
        ao = struct.unpack_from(">I", buf, p + i * 16 + 12)[0]
        cnt = struct.unpack_from(">H", buf, ao)[0]
        ln = struct.unpack_from(">H", buf, ao + 2)[0]
        if cnt == 0 and ln >= 3:
            old_b = out[co]
            new_b = (old_b + 1) % max_index            # another valid fragment index
            out[co] = new_b
            print(f"  byte poke: record {sid} codeOff={co} byte {old_b} -> {new_b} "
                  f"(payload size UNCHANGED: {len(out):,})")
            return bytes(out)
    raise RuntimeError("no suitable single-line row")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--poke", action="store_true", help="flip ONE code byte, nothing moves")
    ap.add_argument("--no-change", action="store_true", help="rebuild without editing text")
    a = ap.parse_args()
    oo = Oodle(INJ)
    base = AF.parse(BOOT); by_fid = {r["ts"]: r for r in base["recs"]}
    entries = []

    for fid in ATLAS_FILEIDS:
        obj = open(os.path.join(HEATLAS, f"{fid:08x}.bin"), "rb").read()[20:]
        br = by_fid[fid]
        with open(BOOT, "rb") as f:
            f.seek(br["offset"]); bb = f.read(br["size"])
        cinfo = bb[8:15]
        c0 = bytearray(CFD.decode_resource(bb, oo)[0][0][0])
        struct.pack_into("<I", c0, 10, len(obj))
        entries.append((fid, br["flags"], br["hash"],
                        build_cfd_raw(bytes(c0), cinfo) + build_cfd_raw(obj, cinfo)))

    # UI: original payload, but RE-WRAPPED RAW. Shipping the record's ORIGINAL
    # Oodle-COMPRESSED bytes through patch_02 black-screens even when nothing else changes
    # (proven by a zero-change control) — patch_02 records must be stored RAW, the same law
    # that governs the loc and atlas records.
    br = by_fid[UI_FILEID]
    with open(BOOT, "rb") as f:
        f.seek(br["offset"]); bb = f.read(br["size"])
    _c = CFD.decode_resource(bb, oo)[0]
    _c0 = bytearray(_c[0][0]); _o = bytes(_c[1][0])
    struct.pack_into("<I", _c0, 10, len(_o))
    entries.append((UI_FILEID, br["flags"], br["hash"],
                    build_cfd_raw(bytes(_c0), _c[0][1]) + build_cfd_raw(_o, _c[1][1])))
    print(f"UI   0x{UI_FILEID:08x}: original payload, re-wrapped RAW")

    br = by_fid[SUBS_FILEID]
    with open(BOOT, "rb") as f:
        f.seek(br["offset"]); bb = f.read(br["size"])
    cfds, _ = CFD.decode_resource(bb, oo)
    cfd0_data, cinfo0 = cfds[0]
    obj, cinfo1 = bytes(cfds[1][0]), cfds[1][1]
    m = obj.find(LP.MARKER)
    old_num = struct.unpack_from("<i", obj, m + 4)[0]
    print(f"SUBS 0x{SUBS_FILEID:08x}:")
    if a.poke:
        payload = byte_poke(obj[m + 8:m + 8 + old_num])
    else:
        payload = surgical(obj[m + 8:m + 8 + old_num], not a.no_change)
    new_obj = bytearray(obj[:m + 4] + struct.pack("<i", len(payload)) + payload
                        + obj[m + 8 + old_num:])
    # obj@4 is NOT len(obj)-51: the constant is (markerOffset - 33), which differs per
    # record (UI marker@84 -> 51, SUBS marker@86 -> 53). Hardcoding 51 wrote a value 2
    # too large for the subtitle package, so the engine read past the payload and span
    # forever. Preserve the ORIGINAL delta instead.
    struct.pack_into("<I", new_obj, 4,
                     (len(new_obj) - (len(obj) - struct.unpack_from("<I", obj, 4)[0]))
                     & 0xFFFFFFFF)
    c0 = bytearray(cfd0_data); struct.pack_into("<I", c0, 10, len(new_obj))
    entries.append((SUBS_FILEID, br["flags"], br["hash"],
                    build_cfd_raw(bytes(c0), cinfo0) + build_cfd_raw(bytes(new_obj), cinfo1)))

    ua = open(UA, "rb").read(); ui = AF.parse(UA); urecs = ui["recs"]
    first_off = urecs[0]["offset"]
    entries += [(r["ts"], r["flags"], r["hash"], ua[r["offset"]:r["offset"] + r["size"]])
                for r in urecs[2:]]
    out = bytearray(ua[:first_off]); toc = bytearray(); off = first_off
    for fid, flags, h, blob in entries:
        toc += struct.pack("<QIIII", off, fid, flags, len(blob), h)
        out += blob; off += len(blob)
    toc_off = off; out += toc; out += ua[ui["toc"] + ui["count"] * AF.REC:]
    struct.pack_into("<I", out, AF.DESC_OFF, len(entries))
    struct.pack_into("<Q", out, AF.DESC_OFF + 4, toc_off)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(out)
    v = AF.parse(OUT); g, t = AF.invariant(v["recs"])
    print(f"\nwrote {len(entries)} records, {len(out):,} B, contiguity {g}/{t}")
    if a.deploy:
        import shutil
        shutil.copyfile(OUT, os.path.join(GAME, "DataPC_boot_patch_02.forge"))
        print("  DEPLOYED")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
