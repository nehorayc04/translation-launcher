#!/usr/bin/env python3
"""
SUBTITLE PROOF for AC Black Flag Resynced — the AC-Origins `id % 3` ladder.

Replaces EVERY Arabic subtitle row (fileID 0x668047c6) with a test string, rotating by
id%3 so three different variants land on ADJACENT lines of the same conversation and one
screenshot settles everything.

  id%3==0  ZZ0  Hebrew stored LOGICAL   -> correct if the engine applies bidi here
  id%3==1  ZZ1  Hebrew stored VISUAL    -> correct if it does NOT (mirror of the above)
  id%3==2  ZZ2  layout row: punctuation, digits, Latin island, and a long tail that must
                wrap — checks in-line layout AND wrap/line ORDER (the Origins trap)

Traps carried over from Origins:
 * the marker must be MEANINGLESS to the engine — `[N]` was swallowed there as a control-name
   substitution, so markers here are bare `ZZn` (Latin+digits, proven to render in this slot).
 * bidi is proven PER SURFACE — the UI being correct does not settle subtitles.
 * Hebrew renders through the repurposed Arabic carrier slots, so the text is carrier-encoded;
   Latin, digits and punctuation pass through untouched.

    python work/build_subtitle_proof.py --deploy
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
L2 = _load("acbf_locpkg2")
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

CARRIER = {chr(int(k, 16)): chr(int(v, 16))
           for k, v in json.load(open(os.path.join(HERE, "carrier_map.json"))).items()}


def enc(t):
    """Hebrew letters -> Arabic carrier codepoints; everything else untouched."""
    return "".join(CARRIER.get(c, c) for c in t)


def vis(t):
    """Store-VISUAL: reverse the Hebrew runs only (digits/Latin keep their order)."""
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
# in-line layout: punctuation, parens, quotes, digits, a Latin island
LAYOUT = 'ZZ2 עברית "מרכאות" (סוגריים) 12.5% ABC - מקף, נקודה. שאלה?'
# the WRAP row is long on purpose, but a multi-line record's code stream is capped at
# 64 KB (u16 cumCodeEnd), so it may only appear on a sparse subset of lines.
WRAP = ('ZZ3 שורה ארוכה במיוחד שנועדה לגלוש לשתי שורות לפחות כדי לבדוק את סדר '
        'השורות בגלישה - הראשונה צריכה להופיע למעלה ולא למטה. סוף!')


def variant(idx):
    if idx % 60 == 5:
        return enc(WRAP)                         # sparse: wrap / line-order test
    m = idx % 3
    if m == 0:
        return "ZZ0 " + enc(HEB)                 # LOGICAL
    if m == 1:
        return "ZZ1 " + enc(vis(HEB))            # VISUAL
    return enc(LAYOUT)                           # in-line layout


def build_cfd_raw(data, cinfo):
    BLOCK = CFD.BLOCK
    nb = max(1, (len(data) + BLOCK - 1) // BLOCK)
    bi = bytearray(); cd = bytearray()
    for i in range(nb):
        raw = data[i * BLOCK:(i + 1) * BLOCK]
        bi += struct.pack("<ii", len(raw), len(raw))
        cd += struct.pack("<I", CFD.adler(raw)) + raw
    return struct.pack("<Q", CFD.MAGIC) + cinfo + struct.pack("<i", nb) + bytes(bi) + bytes(cd)


def repack_loc(bblob, oo, mapper):
    """Decode a LocalizationPackage record, rewrite every LINE via mapper, re-encode RAW.

    Uses the full-fidelity codec: a record may hold MANY subtitle lines behind one
    stringID, and the old flat codec merged them into one mega-string (which is what made
    the engine spin forever). mapper(sid, line_index, text) -> new text."""
    cfds, consumed = CFD.decode_resource(bblob, oo)
    assert len(cfds) == 2 and consumed == len(bblob)
    cfd0_data, cinfo0 = cfds[0]
    obj, cinfo1 = bytes(cfds[1][0]), cfds[1][1]
    m = obj.find(LP.MARKER)
    old_num = struct.unpack_from("<i", obj, m + 4)[0]
    P = L2.parse(obj[m + 8:m + 8 + old_num])
    new_recs = []
    nlines = 0
    for sid, lines, aux in P["records"]:
        out = []
        for i, t in enumerate(lines):
            out.append(mapper(sid, nlines, t)); nlines += 1
        new_recs.append((sid, out, aux))
    payload = L2.build(new_recs, max_index=P["max_index"])
    new_obj = bytearray(obj[:m + 4] + struct.pack("<i", len(payload)) + payload + obj[m + 8 + old_num:])
    # obj@4 is NOT len(obj)-51: the constant is (markerOffset - 33), which differs per
    # record (UI marker@84 -> 51, SUBS marker@86 -> 53). Hardcoding 51 wrote a value 2
    # too large for the subtitle package, so the engine read past the payload and span
    # forever. Preserve the ORIGINAL delta instead.
    struct.pack_into("<I", new_obj, 4,
                     (len(new_obj) - (len(obj) - struct.unpack_from("<I", obj, 4)[0]))
                     & 0xFFFFFFFF)
    new_cfd0 = bytearray(cfd0_data)
    struct.pack_into("<I", new_cfd0, 10, len(new_obj) & 0xFFFFFFFF)
    return (build_cfd_raw(bytes(new_cfd0), cinfo0)
            + build_cfd_raw(bytes(new_obj), cinfo1)), nlines


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    oo = Oodle(INJ)
    base = AF.parse(BOOT)
    by_fid = {r["ts"]: r for r in base["recs"]}
    overrides = []

    # the repurposed atlases (Hebrew drawn into rare Arabic ligature slots)
    for fid in ATLAS_FILEIDS:
        obj = open(os.path.join(HEATLAS, f"{fid:08x}.bin"), "rb").read()[20:]
        brec = by_fid[fid]
        with open(BOOT, "rb") as f:
            f.seek(brec["offset"]); bb = f.read(brec["size"])
        cinfo = bb[8:15]
        cfds_b, _ = CFD.decode_resource(bb, oo)
        c0 = bytearray(cfds_b[0][0]); struct.pack_into("<I", c0, 10, len(obj))
        overrides.append((fid, brec["flags"], brec["hash"],
                          build_cfd_raw(bytes(c0), cinfo) + build_cfd_raw(obj, cinfo)))
        print(f"atlas 0x{fid:08x}: {len(obj):,} B")

    # UI — a couple of Hebrew labels act as the "patch actually loaded" control
    brec = by_fid[UI_FILEID]
    with open(BOOT, "rb") as f:
        f.seek(brec["offset"]); bb = f.read(brec["size"])
    ui_pref = {"متابعة": "המשך", "تحميل": "טעינה"}

    def ui_map(sid, idx, s):
        for k, v in ui_pref.items():
            if s.startswith(k) and len(s) <= 40:
                return enc(v)
        return s

    blob, n = repack_loc(bb, oo, ui_map)
    overrides.append((UI_FILEID, brec["flags"], brec["hash"], blob))
    print(f"UI   0x{UI_FILEID:08x}: {n:,} LINES (control labels only)")

    # SUBTITLES — every row replaced by the id%3 ladder
    brec = by_fid[SUBS_FILEID]
    with open(BOOT, "rb") as f:
        f.seek(brec["offset"]); bb = f.read(brec["size"])
    counts = {0: 0, 1: 0, 2: 0}

    # ACBF_SUBS_PASSTHRU=1 re-encodes the subtitle package with its ORIGINAL text.
    # Isolates "does re-encoding this package at all break the game" from "is my
    # ladder content the problem" — one launch, clean split.
    passthru = os.environ.get("ACBF_SUBS_PASSTHRU") == "1"

    # ACBF_SUBS_KEEP_MULTI=1 keeps the ORIGINAL text of the multi-line dialogue records
    # (still re-encoded against the new fragment table) and only swaps the single-line
    # rows. Splits "re-encoding multi-line records at all" from "my replacement text in
    # them". NB: text in multi-line records cannot be passed through as raw bytes — the
    # original code stream indexes the ORIGINAL fragment table, which a rebuild replaces.
    keep_multi = os.environ.get("ACBF_SUBS_KEEP_MULTI") == "1"
    multi_sids = {sid for sid, lines, _ in L2.parse(
        (lambda o: o[o.find(LP.MARKER) + 8:o.find(LP.MARKER) + 8 + struct.unpack_from(
            "<i", o, o.find(LP.MARKER) + 4)[0]])(bytes(CFD.decode_resource(bb, oo)[0][1][0]))
    )["records"] if len(lines) > 1}

    def sub_map(sid, idx, s):
        counts[idx % 3] += 1
        if passthru:
            return s
        if keep_multi and sid in multi_sids:
            return s
        return variant(idx)

    if os.environ.get("ACBF_SUBS_VERBATIM") == "1":
        # ship the subtitle record with its payload untouched (only re-wrapped RAW).
        # Splits "can this record be overridden at all" from "is my re-encoding valid".
        cfds_s, _ = CFD.decode_resource(bb, oo)
        c0 = bytearray(cfds_s[0][0]); objs = bytes(cfds_s[1][0])
        struct.pack_into("<I", c0, 10, len(objs))
        blob = build_cfd_raw(bytes(c0), cfds_s[0][1]) + build_cfd_raw(objs, cfds_s[1][1])
        n = 0
        print("SUBS: VERBATIM passthrough (payload untouched)")
    else:
        blob, n = repack_loc(bb, oo, sub_map)
    overrides.append((SUBS_FILEID, brec["flags"], brec["hash"], blob))
    print(f"SUBS 0x{SUBS_FILEID:08x}: {n:,} LINES replaced -> "
          f"ZZ0(logical)={counts[0]}  ZZ1(visual)={counts[1]}  ZZ2(layout)={counts[2]}")

    # assemble patch_02 on the UA scaffold
    ua = open(UA, "rb").read(); ui = AF.parse(UA); urecs = ui["recs"]
    first_off = urecs[0]["offset"]
    out = bytearray(ua[:first_off]); toc = bytearray(); off = first_off
    entries = list(overrides) + [(r["ts"], r["flags"], r["hash"],
                                  ua[r["offset"]:r["offset"] + r["size"]]) for r in urecs[2:]]
    for fid, flags, h, blob in entries:
        toc += struct.pack("<QIIII", off, fid, flags, len(blob), h)
        out += blob; off += len(blob)
    toc_off = off; out += toc; out += ua[ui["toc"] + ui["count"] * AF.REC:]
    struct.pack_into("<I", out, AF.DESC_OFF, len(entries))
    struct.pack_into("<Q", out, AF.DESC_OFF + 4, toc_off)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(out)
    v = AF.parse(OUT); g, t = AF.invariant(v["recs"])
    print(f"\nwrote {OUT}\n  {len(entries)} records, {len(out):,} B, contiguity {g}/{t}")

    if a.deploy:
        import shutil
        shutil.copyfile(OUT, os.path.join(GAME, "DataPC_boot_patch_02.forge"))
        print("  DEPLOYED")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
