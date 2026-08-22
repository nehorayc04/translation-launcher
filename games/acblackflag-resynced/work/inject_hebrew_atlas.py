#!/usr/bin/env python3
"""
Inject Hebrew glyphs into the ARABIC baked glyph atlases.

Why this and not the TTF: the engine runs TWO text pipelines. The English/Latin slot
rasterises from a font at runtime (which is why Hebrew renders there), but the ARABIC
slot reads ONLY the baked atlas (class 0xCBD4939A) — proven by elimination: overwriting
every Arabic glyph outline in every embedded/loose TTF changed nothing in-game.

Shortcut used here: the Thai community mod's rebuilt atlas already contains 52 finished
Hebrew glyphs (U+05B0..U+05F4) that the game demonstrably loads. We copy those records
and their SDF rasters byte-for-byte into the three Arabic atlases — no glyph baking, no
SDF calibration, no font matching.

Targets (the three Arabic weights):
    70970 fileID 0x88c902b3 · 70971 0x88c902b5 · 70972 0x88c902b1
Hebrew is appended to face0 (the Arabic face) and, as cheap insurance, to the Latin face
inside the same file — it is not known which face the engine picks for an unmapped script.

    python work/inject_hebrew_atlas.py            # build -> work/heatlas/<fileID>.bin
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import acbf_gfof as G  # noqa: E402

ATLAS = os.path.join(HERE, "atlas")
OUT = os.path.join(HERE, "heatlas")
DONOR = os.path.join(ATLAS, "TH_88c2952a.bin")

TARGETS = ["70970_88c902b3.bin", "70971_88c902b5.bin", "70972_88c902b1.bin"]

HEB_LO, HEB_HI = 0x0590, 0x05FF
HEBPRES_LO, HEBPRES_HI = 0xFB1D, 0xFB4F      # Hebrew presentation forms the donor also has


def latin_face_index(info):
    """The face whose codepoints are mostly Latin — our insurance target."""
    best, best_score = None, -1
    for i, f in enumerate(info["faces"]):
        if not f["recs"]:
            continue
        lat = sum(1 for r in f["recs"] if 0x20 <= r[0] <= 0x24F)
        if lat > best_score:
            best, best_score = i, lat
    return best


def main():
    os.makedirs(OUT, exist_ok=True)
    dbuf = open(DONOR, "rb").read()
    dinfo = G.parse(dbuf)
    dg = dinfo["gfof"]
    donor_recs = [r for f in dinfo["faces"] for r in f["recs"]]
    heb = [r for r in donor_recs
           if HEB_LO <= r[0] <= HEB_HI or HEBPRES_LO <= r[0] <= HEBPRES_HI]
    heb.sort(key=lambda r: r[0])
    letters = [r for r in heb if 0x05D0 <= r[0] <= 0x05EA]
    print(f"donor {os.path.basename(DONOR)}: {len(heb)} Hebrew glyphs "
          f"({len(letters)} of the 27 letters)")
    heb_rasters = [G.raster(dbuf, dg, r) for r in heb]

    for name in TARGETS:
        path = os.path.join(ATLAS, name)
        buf = open(path, "rb").read()
        info = G.parse(buf)
        g = info["gfof"]
        lat_i = latin_face_index(info)

        faces_recs, rasters = [], []
        for fi, f in enumerate(info["faces"]):
            recs = list(f["recs"])
            rs = [G.raster(buf, g, r) for r in recs]
            # CODEPOINTS ARE GLOBALLY UNIQUE across faces in every shipped atlas AND in
            # the third-party mod's atlas (verified: 0 duplicates in all of them).
            # Adding Hebrew to BOTH the Arabic and the Latin face produced 94 duplicate
            # codepoints and CRASHED the game right after the intro logo. Inject into the
            # Arabic face ONLY.
            if fi == 0:
                have = {r[0] for fx in info["faces"] for r in fx["recs"]}   # GLOBAL set
                for r, data in zip(heb, heb_rasters):
                    if r[0] in have:
                        continue
                    recs.append(r); rs.append(data)
            faces_recs.append(recs); rasters.append(rs)

        out = G.build(buf, faces_recs, rasters)
        dst = os.path.join(OUT, name.split("_")[1])
        open(dst, "wb").write(out)
        added = sum(len(fr) for fr in faces_recs) - sum(f["cnt"] for f in info["faces"])
        print(f"\n{name}: face0 + latin face{lat_i}; +{added} glyphs; "
              f"{len(buf):,} -> {len(out):,} B")
        G.check(out, label="rebuilt")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
