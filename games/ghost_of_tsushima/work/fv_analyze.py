#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_analyze.py — round-2 FontVerts crack, analyzing the RIGHT file: ghost_title.xpps.
Loads the cached 10MB ghost_title.bin, finds the multi-script glyph table(s), and dumps
the reference fields for REAL glyphs (Arabic, Hebrew-points) vs degenerate Hebrew letters.
Goal: understand what (+14,+16,+18) references + locate the external FontVerts buffer.
No game file is touched; read-only on the cached bin."""
import os, sys, struct
import numpy as np

CACHE = r"C:/Users/NEHORA~1/AppData/Local/Temp/claude/c--Users-Nehoray-Cohen-Projects-Game-translator/a86ff9b5-d140-4c99-b5de-33e68113ffe9/scratchpad"
GT = os.path.join(CACHE, "ghost_title.bin")
GREC = 64


def load():
    with open(GT, "rb") as f:
        return f.read()


def u16(d, p): return struct.unpack_from("<H", d, p)[0]
def u32(d, p): return struct.unpack_from("<I", d, p)[0]
def f32(d, p): return struct.unpack_from("<f", d, p)[0]


def find_tables(d):
    """RELAXED walker: stride-64 ascending runs where +2==0 and +62==0xffff."""
    n = len(d)
    b = np.frombuffer(d, dtype=np.uint8)
    cand = np.nonzero((b[2:n - 1] == 0) & (b[3:n] == 0))[0]
    out = []
    used = set()
    for pp in cand:
        p = int(pp)
        if p in used or p + GREC > n:
            continue
        if u16(d, p + 62) != 0xffff:
            continue
        cp0 = u16(d, p)
        if not (1 <= cp0 <= 0xfffe):
            continue
        # skip if predecessor is an ascending rec (anchor at true start)
        if p - GREC >= 0 and u16(d, p - GREC + 62) == 0xffff and u16(d, p - GREC + 2) == 0:
            pc = u16(d, p - GREC)
            if pc < cp0 and pc >= 1:
                continue
        cps = []
        q = p
        while q + GREC <= n and u16(d, q + 2) == 0 and u16(d, q + 62) == 0xffff:
            c = u16(d, q)
            if c == 0xffff:
                used.add(q); q += GREC; break
            if not (1 <= c <= 0xfffe):
                break
            if cps and c <= cps[-1]:
                break
            cps.append(c); used.add(q); q += GREC
        if len(cps) >= 12:
            out.append((p, cps, q))
    out.sort(key=lambda t: t[0])
    return out


def dump_rec(d, p, label=""):
    cp = u16(d, p)
    ch = chr(cp) if 32 <= cp < 127 else ""
    print(f"  @0x{p:x} cp=0x{cp:04x} {ch:1} | "
          f"+4f={f32(d,p+4):.3f} +8={u32(d,p+8)} +12={u16(d,p+12)} +14={u16(d,p+14)} "
          f"+16={u16(d,p+16)} +18={u16(d,p+18)} +20={u16(d,p+20):#x} {label}")
    print(f"        geom +22..+45: {d[p+22:p+46].hex()}")
    print(f"        6f: {[round(x,2) for x in struct.unpack_from('<6f', d, p+22)]}")


def main():
    d = load()
    print(f"ghost_title.bin {len(d):,}B magic={d[:4]!r}")
    tbls = find_tables(d)
    print(f"\n{len(tbls)} glyph tables (relaxed):")
    tot_recs = 0
    for s, cps, e in tbls:
        tot_recs += len(cps)
    print(f"  total glyph records across tables: {tot_recs}")
    for s, cps, e in sorted(tbls, key=lambda t: t[0]):
        heb = sum(1 for c in cps if 0x5d0 <= c <= 0x5ea)
        hebp = sum(1 for c in cps if 0x591 <= c <= 0x5c7)
        ar = sum(1 for c in cps if 0x600 <= c <= 0x6ff)
        tag = []
        if heb: tag.append(f"HEB={heb}")
        if hebp: tag.append(f"HEBpt={hebp}")
        if ar: tag.append(f"AR={ar}")
        print(f"  @0x{s:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}] {' '.join(tag)}")

    # ---- find the sub-table covering Hebrew + Hebrew-points + early Arabic
    heb_tbl = None
    for s, cps, e in tbls:
        if any(0x5d0 <= c <= 0x5ea for c in cps):
            heb_tbl = (s, cps, e)
            break
    if not heb_tbl:
        print("\n!! no Hebrew-letter table found"); return
    s, cps, e = heb_tbl
    print(f"\n=== Hebrew-containing sub-table @0x{s:x} n={len(cps)} cp[0x{min(cps):x}..0x{max(cps):x}] ===")

    # map cp -> record offset
    cp2off = {}
    q = s
    for c in cps:
        cp2off[c] = q
        q += GREC

    print("\n--- Hebrew LETTERS 0x5d0..0x5ea (expect degenerate: few distinct refs) ---")
    refs_heb = []
    for c in range(0x5d0, 0x5eb):
        if c in cp2off:
            p = cp2off[c]
            refs_heb.append((u16(d, p + 14), u16(d, p + 16), u16(d, p + 18)))
            dump_rec(d, p, f"HEB U+{c:04X}")
    print(f"  distinct (+14,+16,+18) among Hebrew letters: {len(set(refs_heb))} -> {sorted(set(refs_heb))}")

    print("\n--- Hebrew POINTS 0x591..0x5c7 (expect real: many distinct refs) ---")
    refs_pt = []
    shown = 0
    for c in range(0x591, 0x5c8):
        if c in cp2off:
            p = cp2off[c]
            refs_pt.append((u16(d, p + 14), u16(d, p + 16), u16(d, p + 18)))
            if shown < 8:
                dump_rec(d, p, f"HEBpt U+{c:04X}")
                shown += 1
    print(f"  distinct (+14,+16,+18) among {len(refs_pt)} Hebrew points: {len(set(refs_pt))}")

    # ---- Arabic real table
    ar_tbl = None
    for s2, cps2, e2 in tbls:
        arc = sum(1 for c in cps2 if 0x620 <= c <= 0x6ff)
        if arc >= 20 and s2 != s:
            ar_tbl = (s2, cps2, e2)
            break
    if ar_tbl:
        s2, cps2, e2 = ar_tbl
        cp2off2 = {}
        q = s2
        for c in cps2:
            cp2off2[c] = q; q += GREC
        print(f"\n=== Arabic-letter sub-table @0x{s2:x} n={len(cps2)} cp[0x{min(cps2):x}..0x{max(cps2):x}] ===")
        refs_ar = []
        shown = 0
        for c in sorted(cps2):
            p = cp2off2[c]
            refs_ar.append((u16(d, p + 14), u16(d, p + 16), u16(d, p + 18)))
            if shown < 10:
                dump_rec(d, p, f"AR U+{c:04X}")
                shown += 1
        print(f"  distinct (+14,+16,+18) among {len(refs_ar)} Arabic letters: {len(set(refs_ar))}")

    # ---- global stats on +14 and +16 across every glyph record in every table
    print("\n=== GLOBAL +14 / +16 / +18 stats across all tables ===")
    all14, all16, all18 = [], [], []
    for s3, cps3, e3 in tbls:
        q = s3
        for c in cps3:
            all14.append(u16(d, q + 14)); all16.append(u16(d, q + 16)); all18.append(u16(d, q + 18))
            q += GREC
    import collections
    print(f"  +14 distinct values: {sorted(set(all14))[:40]}  (n={len(set(all14))})")
    print(f"  +16 range: {min(all16)}..{max(all16)}   distinct={len(set(all16))}")
    print(f"  +18 range: {min(all18)}..{max(all18)}   distinct={len(set(all18))}")
    # +14 histogram
    h14 = collections.Counter(all14)
    print(f"  +14 histogram (top): {h14.most_common(12)}")


if __name__ == "__main__":
    main()
