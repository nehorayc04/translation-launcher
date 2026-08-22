#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe2.py — map ALL glyph tables in m_lm_menu, then scan the whole package for a
FontVerts-shaped buffer (a large contiguous run of plausible 2D vertex floats), and
report the biggest float-cluster regions + what sits right after the glyph tables."""
import os, sys, struct, math
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import got_fonk as GF


def get(archive, name):
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def f32_plausible(x):
    if x != x or math.isinf(x):
        return False
    ax = abs(x)
    return ax == 0.0 or (1e-4 < ax < 1e4)


def scan_float_runs(data, win=64, thresh=0.9, step=4):
    """Find regions where >=thresh of f32 values (stride 4) are 'plausible' coords."""
    n = len(data)
    runs = []
    i = 0
    cur_start = None
    good = 0
    total = 0
    # sliding: mark 4-byte words as plausible float or not
    words = []
    for p in range(0, n - 3, 4):
        x = struct.unpack_from("<f", data, p)[0]
        words.append(f32_plausible(x))
    # find maximal runs with high plausible-density
    start = None
    run_good = 0
    for idx, ok in enumerate(words):
        if ok:
            if start is None:
                start = idx
                run_good = 0
            run_good += 1
        else:
            if start is not None:
                length = idx - start
                if length >= win // 4 and run_good / length >= thresh:
                    runs.append((start * 4, idx * 4, length, run_good / length))
                start = None
    if start is not None:
        length = len(words) - start
        if length >= win // 4:
            runs.append((start * 4, len(words) * 4, length, 1.0))
    return runs


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    print(f"m_lm_menu size={len(data):,}")
    tbls = GF.find_rich_tables(data, min_run=8)
    print(f"\nRICH glyph tables found: {len(tbls)}")
    for s, cps, e in sorted(tbls):
        print(f"  @0x{s:x}..0x{e:x}  n={len(cps)}  cp[0x{min(cps):x}..0x{max(cps):x}]  size={e-s}")

    # biggest float-run regions
    runs = scan_float_runs(data)
    runs.sort(key=lambda r: -r[2])
    print(f"\nBiggest plausible-float regions (candidate FontVerts / mesh):")
    for a, b, ln, dens in runs[:15]:
        print(f"  @0x{a:x}..0x{b:x}  words={ln}  density={dens:.2f}  bytes={b-a:,}")

    # for each glyph table, dump 48 bytes right after the table end
    print("\n== bytes right AFTER each glyph table (looking for a vert buffer / header) ==")
    for s, cps, e in sorted(tbls):
        seg = data[e:e + 48]
        print(f"  after 0x{e:x}: {seg[:48].hex()}")


if __name__ == "__main__":
    main()
