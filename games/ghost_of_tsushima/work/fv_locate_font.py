#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_locate_font.py — LOCATE every glyph-record table across the game. The distinctive
glyph-record tail = 4-float white colour (G,B,A = 1.0) + 0xffff sentinel:
    00 00 80 3f  00 00 80 3f  00 00 80 3f  ff ff   (record +50..+63)
Count it per .xpps across all psarcs (skip the 965MB audio). For files with many hits,
report the biggest glyph table + whether it has REAL letter metrics (non-ramp) and the
codepoint coverage (does it reach Arabic 0x600 / CJK?)."""
import os, sys, struct
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import got_fonk as GF

TAIL = bytes.fromhex("0000803f0000803f0000803fffff")   # +50..+63 of a glyph record
GREC = 64
SKIP_SUBSTR = ("common_sound",)  # 965MB audio


def main():
    arcs = sorted(f for f in os.listdir(PD) if f.endswith(".psarc"))
    results = []
    for a in arcs:
        try:
            arc = R.Psarc2(os.path.join(PD, a))
        except Exception as e:
            print(f"{a}: open err {e}"); continue
        for e in arc.files():
            name = e.path
            if any(s in name for s in SKIP_SUBSTR):
                continue
            if not name.endswith(".xpps"):
                continue
            if e.orig_size > 700_000_000:
                continue
            try:
                d = arc.extract(e)
            except Exception:
                continue
            c = d.count(TAIL)
            if c >= 8:
                results.append((c, a, name, e.orig_size, d))
        arc.d.f.close()
    results.sort(key=lambda r: -r[0])
    print(f"files with >=8 glyph-record tails: {len(results)}")
    for c, a, name, sz, d in results[:30]:
        # find biggest rich table + real-letter check
        tbls = GF.find_rich_tables(d, min_run=6)
        best = max(tbls, key=lambda t: len(t[1])) if tbls else None
        info = ""
        maxcp = 0
        arb = cjk = 0
        if best:
            s, cps, e = best
            maxcp = max(cps)
            arb = sum(1 for x in cps if 0x590 <= x <= 0x6ff)
            cjk = sum(1 for x in cps if x >= 0x3000)
            # letters real? check metric ramp on cp 0x41..0x5a
            ms = []
            recmap = {}
            q = s
            for x in cps:
                recmap[x] = d[q:q + GREC]; q += GREC
            letters = [x for x in cps if 0x41 <= x <= 0x5a]
            ramp = False
            if len(letters) >= 4:
                lm = [struct.unpack_from("<f", recmap[x], 4)[0] for x in letters]
                deltas = [round(lm[i + 1] - lm[i], 4) for i in range(len(lm) - 1)]
                ramp = len(set(deltas)) <= 2 and all(abs(x) > 1e-4 for x in deltas)
            info = f"tables={len(tbls)} bigT@0x{s:x} n={len(cps)} cp<=0x{maxcp:x} AR/HE={arb} CJK={cjk} lettersRamp={ramp}"
        print(f"  {c:>5} tails  {a:26s} {name:40s} {sz:>12,}  {info}")


if __name__ == "__main__":
    main()
