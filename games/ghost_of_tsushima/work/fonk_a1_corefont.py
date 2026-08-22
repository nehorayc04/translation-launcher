#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_corefont.py — in core_common.sprig.xpps, enumerate the 64-byte glyph
tables, find the one(s) with Arabic coverage (the Hebrew-injection target), and test
whether the per-glyph geometry region is UV-into-atlas [0,1] (=> atlas font)."""
import os, sys, struct
import numpy as np

GAME = r"F:/Games/Ghost of Tsushima DC"
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R
R_ = 64


def get(archive, name):
    arc = R.Psarc2(os.path.join(PSARC_DIR, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def tables_from(data):
    """Find 64-byte glyph tables: scan for cp 'A' at stride 64 with B,C,D following,
    then walk back/forward to bound each table. Return list of (start,end,cps)."""
    b = np.frombuffer(data, dtype=np.uint8)
    aidx = np.nonzero((b[:-1] == 0x41) & (b[1:] == 0x00))[0]
    seeds = []
    for p in aidx:
        p = int(p)
        if p+4*R_+2 <= len(data) and all(
                struct.unpack_from("<H", data, p+k*R_)[0] == 0x41+k for k in range(1,4)):
            seeds.append(p)
    tables = []
    used = set()
    for s in seeds:
        # walk back
        p = s
        while p-R_ >= 0:
            a = struct.unpack_from("<H", data, p-R_)[0]
            c = struct.unpack_from("<H", data, p)[0]
            if a == c-1 and 0x1 <= a <= 0x6ff: p -= R_
            else: break
        if p in used: continue
        # walk forward while ascending
        q = p; cps = []
        while q+R_ <= len(data):
            cp = struct.unpack_from("<H", data, q)[0]
            if cps and not (cp > cps[-1]): break
            if cp == 0xffff: cps.append(cp); q += R_; break
            if not (0x1 <= cp <= 0xfffe): break
            cps.append(cp); q += R_
        used.add(p)
        tables.append((p, q, cps))
    return tables


def main():
    data = get("gapack_misc_c.psarc", "core_common.sprig.xpps")
    print(f"core_common.sprig.xpps {len(data):,} B")
    tbls = tables_from(data)
    print(f"found {len(tbls)} candidate 64-byte glyph tables")
    # summarize coverage per table; flag Arabic/Hebrew
    def cnt(cps,a,b): return sum(1 for c in cps if a<=c<=b)
    arabic_tbls = []
    for (s,e,cps) in tbls:
        real = [c for c in cps if c != 0xffff]
        if not real: continue
        ar = cnt(real,0x600,0x6ff); he = cnt(real,0x5d0,0x5ea)
        cjk = cnt(real,0x3000,0xffff); asc = cnt(real,0x20,0x7e)
        if ar or he or cjk>5 or len(real)>150:
            print(f"   @0x{s:x} n={len(real)} min=0x{min(real):x} max=0x{max(real):x} "
                  f"ASCII={asc} Arabic={ar} Hebrew={he} CJK={cjk}")
        if ar: arabic_tbls.append((s,e,real,ar))
    print(f"\n== {len(arabic_tbls)} tables with Arabic coverage ==")
    if arabic_tbls:
        s,e,cps,ar = max(arabic_tbls, key=lambda t:t[3])
        print(f"   biggest-Arabic table @0x{s:x}: {len(cps)} glyphs, {ar} Arabic")
        # show the Arabic records + test geometry region for UV [0,1]
        arabic_recs = [(i,c) for i,c in enumerate(cps) if 0x600<=c<=0x6ff][:4]
        for idx,cp in arabic_recs:
            r = data[s+idx*R_:s+idx*R_+R_]
            f32 = struct.unpack_from("<16f", r, 0)
            print(f"   cp=0x{cp:x}: {r.hex()}")
            # candidate UV floats: which f32 are in [0,1]?
            uv = [(k*4, round(v,4)) for k,v in enumerate(f32) if 0.0 <= v <= 1.0 and v!=0.0]
            print(f"      f32 in (0,1]: {uv}")

    # geometry test on Latin 'A' too (from m_lm_menu format): are +22..+48 floats UV?
    print("\n== does core have a font-atlas texture nearby? search .sps refs / SBitmap type ==")
    for tag in (b"SBitmap", b"atlas", b"Atlas", b".sps"):
        c = data.count(tag)
        i = data.find(tag)
        print(f"   {tag!r}: x{c} first@{('0x%x'%i) if i>=0 else '-'}")


if __name__ == "__main__":
    main()
