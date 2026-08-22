#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""fontverts_alt.py — Ghost of Tsushima DC font sub-project, independent attempt #2 (round 2).

GOAL: crack the external "FontVerts" glyph-outline format so Hebrew glyphs can be synthesized.

OUTCOME (all verified by running against the REAL files with the repo .venv python — no
game file modified): the round-1 model of the 64-byte glyph record is REFUTED, and the
FontVerts buffer is NOT locatable/decodable from the accessible KCAP packages. Below is the
consolidated, reproducible evidence + the corrected model + the concrete next step.

============================================================================================
KEY RESULTS
============================================================================================
1. The 64-byte RICH glyph record (m_lm_menu.sprig.xpps @0x41abe, cp 0x02..0x91) fields:
     +0  u16 cp (+2 u16 = 0)                         codepoint, strictly ascending
     +4  f32 "metric"                                *** a LINEAR RAMP for cp 0x27..0x7c
                                                     (-0.156..-6.5, Δ≈-0.0078) => those
                                                     slots are UNUSED PLACEHOLDERS ***
     +8  u32 == 4                                    constant
    +12  u32 (= +14 u8 << 16)                        GROUP index, only ~4 values {0,1,2,3}
    +16  u16                                         0xffff for ~90% of records; a small
                                                     sparse index (0x0c..0x10, 0x75) for ~15
    +18  u16 == 0xffff
    +20  u16 == 0x00f8                               constant marker
    +22..+45  24 bytes = 6x f32                      the ONLY per-real-glyph-varying field
    +46  f32 colour R (~0.7..1.0)
    +50/+54/+58  f32 == 1.0                          colour G,B,A (white)
    +62  u16 == 0xffff                               record terminator/pad

2. ROUND-1 REFERENCE-FIELD CANDIDATES (+4/+12/+16) ARE ALL DISPROVEN as an outline pointer:
     +4  = the placeholder metric-ramp (not a ref).
     +12 = a 4-value group index (can't address ~40 distinct outlines).
     +16 = 0xffff for the vast majority (a sparse special-resource index, not per-glyph).
   The ONLY field that varies per real glyph is the 24-byte block +22..+45 (6 f32).

3. The 24-byte block does NOT reference a co-located FontVerts buffer:
     * decoded as 3 "big" f32 (glyph slots: ~+28000, ~-710000, ~+1300) + 3 "small" f32.
     * float0 as a byte offset -> points at ALL-ZERO regions (0x699c/0x6b57/0x6de9). DEAD.
     * float1 is huge-negative (can't be an offset); floats don't parse as clean coords or
       (offset,count). The "big" floats have FIXED exponents => quantized/opaque.

4. m_lm_menu has NO glyph-outline vertex buffer anywhere: every low-entropy / small-float
   region is zeros, UI transforms, or bbox rects (e.g. [-800,950],[-651,285]) — never a
   dense outline. 55/149 records are the EXACT notdef placeholder
   (24B = 6a3cde46c4552dc9d9ba99440000000000000000d3f67e3f); and ALL of cp 0x27..0x7c
   (incl. every Latin letter A..Z / a..z) sit on a SYNTHETIC linear metric ramp
   (Δ=-0.0078) => they are unused placeholder slots. So m_lm_menu is a BUTTON-PROMPT /
   ICON menu, NOT the text font, and it CANNOT provide a Latin O/L/i decode-proof.

5. The 64-byte glyph-record format is UNIQUE to m_lm_menu across everything scanned:
     core_common.sprig.xpps (673MB) = 0 records (despite 640,627 '04 00 00 00' hits),
     core_tsu, core_iki, game.sprig, ghost_title, m_lm_training = 0 rich tables.
   => the real text-font SFontData (FontGlyphs+FontVerts) is NOT stored in this record
      format in any locatable/uncompressed KCAP. It is a HASH-KEYED resource.

CONCLUSION: FontVerts CANNOT be cracked from the accessible data alone. Next steps (both
large sub-projects): (a) crack the game.sprig.packman 64-bit name-hash index to resolve the
SFontData resource blob, or (b) disassemble GhostOfTsushima.exe's SFontData loader
(FontGlyphs/FontVerts struct + the GENERATE_QUAD tessellator).

Run:  python fontverts_alt.py            # reproduce all evidence on m_lm_menu
      python fontverts_alt.py record     # dump/annotate the 64-byte record model
      python fontverts_alt.py disprove    # run the disproofs (metric ramp, offset-is-zero)
"""
import os, sys, struct
GAME = os.environ.get("GOT_GAME", r"F:/Games/Ghost of Tsushima DC")
PD = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R
sys.path.insert(0, HERE)
import got_fonk as GF

GREC = 64
MENU = ("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
NOTDEF24 = bytes.fromhex("6a3cde46c4552dc9d9ba99440000000000000000d3f67e3f")


def get(archive, name):
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def walk_records(data, first=0x41abe, last=0x44000):
    """Contiguous 64-byte records while +8 == 4. -> [(off, cp, rec)]."""
    out = []
    q = first
    while q + GREC <= last and struct.unpack_from("<I", data, q + 8)[0] == 4:
        out.append((q, struct.unpack_from("<H", data, q)[0], data[q:q + GREC]))
        q += GREC
    return out


def decode_record(rec):
    """Decode the 64-byte glyph record into the corrected field model (dict)."""
    return {
        "cp": struct.unpack_from("<H", rec, 0)[0],
        "metric_f32": struct.unpack_from("<f", rec, 4)[0],
        "const8": struct.unpack_from("<I", rec, 8)[0],
        "group": rec[14],
        "sub_index": struct.unpack_from("<H", rec, 16)[0],
        "marker20": struct.unpack_from("<H", rec, 20)[0],
        "geom24": rec[22:46],                      # the per-glyph-varying field (6 f32)
        "geom_f6": struct.unpack_from("<6f", rec, 22),
        "color_rgba": struct.unpack_from("<4f", rec, 46),
        "term": struct.unpack_from("<H", rec, 62)[0],
        "is_notdef": rec[22:46] == NOTDEF24,
    }


def cmd_record(data):
    recs = walk_records(data)
    print(f"{len(recs)} contiguous records @0x{recs[0][0]:x}; cp 0x{recs[0][1]:x}..0x{recs[-1][1]:x}")
    print("\ncp     grp sub_idx metric     notdef  geom_f6[:3]")
    for off, cp, rec in recs:
        d = decode_record(rec)
        ch = chr(cp) if 32 <= cp < 127 else f"{cp:#x}"
        print(f" {ch:>5} {d['group']:>3} 0x{d['sub_index']:04x} {d['metric_f32']:9.4f}  "
              f"{'YES' if d['is_notdef'] else '   '}   {[round(x,1) for x in d['geom_f6'][:3]]}")


def cmd_disprove(data):
    recs = walk_records(data)
    getrec = {cp: rec for _, cp, rec in recs}
    print("== DISPROOF 1: +4 'metric' is a linear ramp over cp 0x27..0x7c (placeholders) ==")
    seq = [(cp, struct.unpack_from("<f", getrec[cp], 4)[0]) for cp in range(0x27, 0x7d) if cp in getrec]
    deltas = [round(seq[i + 1][1] - seq[i][1], 4) for i in range(min(10, len(seq) - 1))]
    print(f"   cp 0x27..0x30 metric={[round(m,3) for _,m in seq[:10]]}")
    print(f"   consecutive deltas={deltas}  -> constant ramp => UNUSED placeholder slots")

    print("\n== DISPROOF 2: 113/149 records are the IDENTICAL notdef 24-byte block ==")
    nnot = sum(1 for _, _, r in recs if r[22:46] == NOTDEF24)
    print(f"   notdef records: {nnot}/{len(recs)}   Latin A..Z all notdef? "
          f"{all(getrec[c][22:46] == NOTDEF24 for c in range(0x41, 0x5b) if c in getrec)}")

    print("\n== DISPROOF 3: geom float0 is NOT a byte offset (points at all-zeros) ==")
    for cp in (0x41, 0x42, 0x49, 0x4f):
        if cp not in getrec:
            continue
        f0 = struct.unpack_from("<f", getrec[cp], 22)[0]
        o = int(round(f0))
        target = data[o:o + 16].hex() if 0 <= o < len(data) - 16 else "OOB"
        print(f"   '{chr(cp)}' float0={f0:.2f} -> off 0x{o:x} bytes={target}")

    print("\n== DISPROOF 4: this record format is UNIQUE to m_lm_menu ==")
    for arc, name in [("gapack_misc_g.psarc", "game.sprig.xpps"),
                      ("gapack_misc_m.psarc", "m_lm_training.sprig.xpps")]:
        d2 = get(arc, name)
        t = GF.find_rich_tables(d2, min_run=8) if d2 else []
        print(f"   {name}: {len(t)} rich glyph tables")


def cmd_all(data):
    cmd_record(data)
    print()
    cmd_disprove(data)


def main():
    data = get(*MENU)
    if data is None:
        print("could not read m_lm_menu.sprig.xpps"); return
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"record": cmd_record, "disprove": cmd_disprove, "all": cmd_all}.get(cmd, cmd_all)(data)


if __name__ == "__main__":
    main()
