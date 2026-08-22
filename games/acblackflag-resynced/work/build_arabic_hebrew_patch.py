#!/usr/bin/env python3
"""
Build the ARABIC-SLOT Hebrew patch_02: overrides BOTH
  (a) the two Noto Kufi Arabic PhoenixFont records, now carrying Hebrew glyphs
      (work/hefonts/*.bin, built by inject_hebrew_font.py), and
  (b) the Arabic UI LocalizationPackage with Hebrew menu strings,
so the engine's native Arabic RTL path renders real Hebrew, right-aligned.

Everything is stored RAW (uncompressed) — the game's Oodle is statically linked and
silently rejects our re-compressed streams (that was the cause of every earlier
"nothing changed" / black screen).

Each override record's TOC `flags` MUST equal the base record's flags
(fonts 0x20f, Arabic loc 0x207) or the game ignores the override.

    python work/build_arabic_hebrew_patch.py            # build
    python work/build_arabic_hebrew_patch.py --deploy   # build + copy into the game
"""
import importlib.util
import os
import struct
import sys
import argparse

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
HEFONTS = os.path.join(HERE, "hefonts")
OUT = os.path.join(HERE, "refmods", "he", "DataPC_boot_patch_02.forge")

ARABIC_UI_FILEID = 0x668047C5          # base idx 27724, flags 0x207
FONT_FILEIDS = [0xB4C3F12B, 0xB4C3F12C]
# The three Arabic baked glyph atlases (class 0xCBD4939A), rebuilt with Hebrew glyphs
# by inject_hebrew_atlas.py. THIS is what the Arabic text path actually reads.
HEATLAS = os.path.join(HERE, "heatlas")
ATLAS_FILEIDS = [0x88C902B3, 0x88C902B5, 0x88C902B1]

PREFIX_HE = {
    "متابعة": "המשך", "عام": "כללי", "خروج": "יציאה", "تحميل": "טעינה",
    "حفظ": "שמירה", "القصة": "עלילה", "الإعدادات": "הגדרות",
}
MAXLEN = 40


class RawOodle:
    def compress(self, data, level=0):
        return bytes(data)

    def decompress(self, data, uncomp):
        return bytes(data)


def build_cfd_raw(data, cinfo):
    """One CFD holding `data` in raw (uncompressed) 262144-byte blocks."""
    BLOCK = CFD.BLOCK
    nb = max(1, (len(data) + BLOCK - 1) // BLOCK)
    bi = bytearray(); cd = bytearray()
    for i in range(nb):
        raw = data[i * BLOCK:(i + 1) * BLOCK]
        bi += struct.pack("<ii", len(raw), len(raw))
        cd += struct.pack("<I", CFD.adler(raw)) + raw
    return struct.pack("<Q", CFD.MAGIC) + cinfo + struct.pack("<i", nb) + bytes(bi) + bytes(cd)


def encode_record(cfd0_bytes, obj_bytes, cinfo):
    """Rebuild a 2-CFD resource blob (CFD0 descriptor + CFD1 object), both raw."""
    return build_cfd_raw(cfd0_bytes, cinfo) + build_cfd_raw(obj_bytes, cinfo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    oo = Oodle(INJ)

    base = AF.parse(BOOT); brecs = base["recs"]
    by_fid = {r["ts"]: (i, r) for i, r in enumerate(brecs)}

    # ---- 1. the two Hebrew-carrying Arabic fonts ----------------------------------
    overrides = []          # (fileID, flags, blob)
    for fid in ([] if os.environ.get('ACBF_NO_FONTS') == '1' else FONT_FILEIDS):
        src = os.path.join(HEFONTS, f"{fid:08x}.bin")
        d = open(src, "rb").read()
        cfd0, obj = d[:20], d[20:]
        _, brec = by_fid[fid]
        # reuse the base record's cinfo so the container metadata is untouched
        with open(BOOT, "rb") as f:
            f.seek(brec["offset"]); bblob = f.read(brec["size"])
        cinfo = bblob[8:15]
        blob = encode_record(cfd0, obj, cinfo)
        overrides.append((fid, brec["flags"], blob))
        print(f"font 0x{fid:08x}: obj {len(obj):,} B -> record {len(blob):,} B (RAW), flags 0x{brec['flags']:x}")

    # ---- 1b. the three Arabic glyph atlases, rebuilt with Hebrew glyphs ------------
    for fid in ATLAS_FILEIDS:
        src = os.path.join(HEATLAS, f"{fid:08x}.bin")
        if not os.path.isfile(src):
            print(f"atlas 0x{fid:08x}: MISSING {src} — run inject_hebrew_atlas.py first")
            return 1
        # the cached atlas .bin is CFD0(20 B) + obj — strip the descriptor, or the
        # rebuilt record ends up with a DUPLICATED CFD0 prefix (crash after the intro).
        # ACBF_ATLAS_PASSTHRU=1 uses the ORIGINAL atlas bytes instead of the Hebrew
        # rebuild — isolates "can we override this resource at all" from "is our
        # rebuilt atlas content valid".
        if os.environ.get("ACBF_ATLAS_PASSTHRU") == "1":
            src = os.path.join(HERE, "atlas", {0x88C902B3: "70970_88c902b3.bin",
                                               0x88C902B5: "70971_88c902b5.bin",
                                               0x88C902B1: "70972_88c902b1.bin"}[fid])
        atlas_obj = open(src, "rb").read()[20:]
        _, brec = by_fid[fid]
        with open(BOOT, "rb") as f:
            f.seek(brec["offset"]); bblob = f.read(brec["size"])
        cinfo = bblob[8:15]
        # the atlas resource is a 2-CFD record: CFD0 = 20-byte descriptor, CFD1 = the atlas
        cfds_b, _ = CFD.decode_resource(bblob, oo)
        cfd0_data = bytearray(cfds_b[0][0])
        struct.pack_into("<I", cfd0_data, 10, len(atlas_obj))
        blob = build_cfd_raw(bytes(cfd0_data), cinfo) + build_cfd_raw(atlas_obj, cinfo)
        overrides.append((fid, brec["flags"], blob))
        print(f"atlas 0x{fid:08x}: obj {len(atlas_obj):,} B -> record {len(blob):,} B (RAW), "
              f"flags 0x{brec['flags']:x}")

    # ---- 2. the Arabic UI localization package, patched to Hebrew -----------------
    lidx, lrec = by_fid[ARABIC_UI_FILEID]
    with open(BOOT, "rb") as f:
        f.seek(lrec["offset"]); lblob = f.read(lrec["size"])
    cfds, consumed = CFD.decode_resource(lblob, oo)
    assert len(cfds) == 2 and consumed == len(lblob)
    cfd0_data, cinfo0 = cfds[0]
    obj, cinfo1 = bytes(cfds[1][0]), cfds[1][1]

    strs = {}
    for pk in LP.find_packages(obj):
        strs.update(pk.get("strings", {}))

    # The atlas cannot GROW (adding records crashes the game), so Hebrew is drawn into
    # repurposed rare Arabic ligature slots. The stored text therefore uses those Arabic
    # CARRIER codepoints: the engine sees a strong-RTL Arabic run (native bidi applies)
    # but paints Hebrew letters.
    carrier = {}
    cpath = os.path.join(HERE, "carrier_map.json")
    if os.path.isfile(cpath):
        import json
        carrier = {chr(int(k, 16)): chr(int(v, 16))
                   for k, v in json.load(open(cpath)).items()}
        print(f"carrier map: {len(carrier)} Hebrew letters -> Arabic slots")

    def enc(t):
        return "".join(carrier.get(ch, ch) for ch in t)

    patch = {}
    for pid, t in strs.items():
        for pref, he in PREFIX_HE.items():
            if t.startswith(pref) and len(t) <= MAXLEN:
                patch[pid] = enc(he)
                break
    print(f"loc 0x{ARABIC_UI_FILEID:08x}: {len(strs):,} strings, patching {len(patch)} to Hebrew")

    m = obj.find(LP.MARKER)
    old_num = struct.unpack_from("<i", obj, m + 4)[0]
    id_text = [(sid, patch.get(sid, s)) for sid, s in strs.items()]
    payload = LP.build_payload(id_text)
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
    lblob_new = build_cfd_raw(bytes(new_cfd0), cinfo0) + build_cfd_raw(bytes(new_obj), cinfo1)
    overrides.append((ARABIC_UI_FILEID, lrec["flags"], lblob_new))
    print(f"   record {len(lblob_new):,} B (RAW), flags 0x{lrec['flags']:x}")

    # ---- 3. assemble patch_02 (UA scaffold: keep its records [2..9], swap [0]) -----
    ua = open(UA, "rb").read()
    ui = AF.parse(UA); urecs = ui["recs"]
    first_off = urecs[0]["offset"]
    header = ua[:first_off]
    tail = ua[ui["toc"] + ui["count"] * AF.REC:]

    entries = []            # (fileID, flags, hash, blob)
    for fid, flags, blob in overrides:
        _, brec = by_fid[fid]
        entries.append((fid, flags, brec["hash"], blob))
    for i in range(2, ui["count"]):          # scaffold records, verbatim
        r = urecs[i]
        entries.append((r["ts"], r["flags"], r["hash"], ua[r["offset"]:r["offset"] + r["size"]]))

    out = bytearray(header)
    toc = bytearray()
    off = first_off
    for fid, flags, h, blob in entries:
        toc += struct.pack("<QIIII", off, fid, flags, len(blob), h)
        out += blob; off += len(blob)
    toc_off = off
    out += toc
    out += tail
    struct.pack_into("<I", out, AF.DESC_OFF, len(entries))
    struct.pack_into("<Q", out, AF.DESC_OFF + 4, toc_off)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(out)
    print(f"\nwrote {OUT}\n  {len(entries)} records, {len(out):,} B")

    v = AF.parse(OUT); g, t = AF.invariant(v["recs"])
    print(f"  verify: count={v['count']} contiguity {g}/{t}")
    for i, r in enumerate(v["recs"][:3]):
        print(f"    [{i}] fileID=0x{r['ts']:08x} flags=0x{r['flags']:x} size={r['size']:,}")

    if a.deploy:
        import shutil
        dst = os.path.join(GAME, "DataPC_boot_patch_02.forge")
        shutil.copyfile(OUT, dst)
        print(f"  DEPLOYED -> {dst}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
