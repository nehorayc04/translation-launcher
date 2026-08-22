#!/usr/bin/env python3
"""
Draw Hebrew into EXISTING Arabic glyph slots — zero growth.

Why: adding records to the atlas crashes the game (verified by isolation: the same
atlas passed through unchanged boots fine, +94 records crashes, and it is not a
duplicate-codepoint problem). So instead of growing the table we REPURPOSE rare
Arabic presentation-form slots: keep each record's W,H (so every raster keeps its
exact byte length and the whole blob layout is untouched — the file size does not
change by a single byte), blit the Hebrew SDF into the slot's canvas, and fix the
float box/advance so the glyph lands in the right place.

The text then stores those Arabic carrier codepoints, so the engine still sees a
strong-RTL Arabic run and applies its native bidi — but draws Hebrew letters.

    python work/repurpose_atlas.py          # -> work/heatlas/<fileID>.bin + carrier_map.json
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import acbf_gfof as G

ATLAS = os.path.join(HERE, "atlas")
OUT = os.path.join(HERE, "heatlas")
DONOR = os.path.join(ATLAS, "TH_88c2952a.bin")
TARGETS = ["70970_88c902b3.bin", "70971_88c902b5.bin", "70972_88c902b1.bin"]
MAPFILE = os.path.join(HERE, "carrier_map.json")

HEB_LETTERS = list(range(0x05D0, 0x05EB))          # 27 letters


def main():
    os.makedirs(OUT, exist_ok=True)
    # Glyphs are BAKED from the game's own AvenirNextWorld-Light at the native cap height
    # (28 px) instead of copied from the Thai mod. Measured on the same atlas, the copied
    # glyphs were 20 px against a 28 px native Latin cap (0.71 - visibly undersized), and
    # came from an unknown face; Light is the exact face+weight the atlas's Latin face uses
    # (advance match 0.000 px) and the closest ink density (0.290 vs the native 0.239).
    import bake_hebrew_sdf as BK
    font = os.environ.get("ACBF_HEB_FONT", r"C:\Windows\Fonts\Assistant-Regular.ttf")
    fp = font if os.path.isabs(font) else os.path.join(BK.RES, font)
    px = int(os.environ["ACBF_HEB_PX"]) if os.environ.get("ACBF_HEB_PX") else BK.em_for_cap(fp)
    baked = BK.bake(fp, px)
    if not baked or len(baked) < 27:
        print(f"bake failed from {font}"); return 1
    print(f"baked {len(baked)}/27 Hebrew letters from {font} @ {px}px (native cap {BK.NATIVE_CAP})")

    # keep the donor records only for their metrics shape; replace raster + box with the bake
    d = open(DONOR, "rb").read()
    di = G.parse(d); dg = di["gfof"]
    heb = {}
    hebraster = {}
    for cp in HEB_LETTERS:
        ch = chr(cp)
        adv, x0, y0, x1, y1, w, h, data = baked[ch]
        heb[cp] = (cp, float(adv), float(x0), float(y0), float(x1), float(y1),
                   float(w), float(h), 0)
        hebraster[cp] = data

    carrier_map = None
    for name in TARGETS:
        buf = open(os.path.join(ATLAS, name), "rb").read()
        info = G.parse(buf); g = info["gfof"]

        # rare Arabic ligature slots, largest first, big enough for any Hebrew letter
        f0 = info["faces"][0]["recs"]
        need_w = max(int(r[6]) for r in heb.values())
        need_h = max(int(r[7]) for r in heb.values())
        # Pick the TIGHTEST slot that still fits, not the largest. Keeping a 367x63 slot for
        # a 30px-wide letter leaves the record's box ~9x wider than its ink (76% of the
        # bitmap is empty vs 40% in native glyphs) — the engine sizes/samples the glyph from
        # that box, so an oversized box renders as a coarse, "upscaled low-res" edge.
        cands = [r for r in f0 if 0xFB50 <= r[0] <= 0xFDFF
                 and int(r[6]) >= need_w and int(r[7]) >= need_h]
        cands.sort(key=lambda r: int(r[6]) * int(r[7]))          # smallest sufficient first
        picks = cands[:27]
        if len(picks) < 27:
            print(f"{name}: only {len(picks)} slots"); return 1
        if carrier_map is None:                       # same mapping for all 3 weights
            carrier_map = {f"{cp:04X}": f"{picks[i][0]:04X}"
                           for i, cp in enumerate(HEB_LETTERS)}
        assign = {int(v, 16): int(k, 16) for k, v in carrier_map.items()}   # arabicCp -> hebCp

        faces_recs, rasters = [], []
        for fi, f in enumerate(info["faces"]):
            recs, rs = [], []
            for r in f["recs"]:
                data = G.raster(buf, g, r)
                if fi == 0 and r[0] in assign:
                    hcp = assign[r[0]]
                    hr = heb[hcp]; hras = hebraster[hcp]
                    W, H = int(r[6]), int(r[7])
                    hW, hH = int(hr[6]), int(hr[7])
                    canvas = bytearray(W * H)          # 0 = far outside in this SDF
                    for row in range(hH):              # blit at top-left
                        canvas[row * W:row * W + hW] = hras[row * hW:(row + 1) * hW]
                    data = bytes(canvas)
                    # keep W,H (byte size identical); move the box so the ink lands right
                    x0 = hr[2]; y1 = hr[5]
                    r = (r[0], hr[1], x0, y1 - H, x0 + W, y1, float(W), float(H), r[8])
                recs.append(r); rs.append(data)
            faces_recs.append(recs); rasters.append(rs)

        out = G.build(buf, faces_recs, rasters)
        assert len(out) == len(buf), f"size changed {len(buf)} -> {len(out)}"
        open(os.path.join(OUT, name.split("_")[1]), "wb").write(out)
        print(f"{name}: 27 slots repurposed; size UNCHANGED ({len(out):,} B)")
        G.check(out, label="  rebuilt")

    json.dump(carrier_map, open(MAPFILE, "w"), indent=1)
    print("\ncarrier map -> carrier_map.json")
    for k, v in list(carrier_map.items())[:6]:
        print(f"   U+{k} {chr(int(k,16))}  ->  U+{v}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
