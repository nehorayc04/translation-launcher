#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fonk_a1_glyphtable.py — decode the REAL 64-byte glyph record + table header, and
map codepoint coverage (Latin? Arabic? Hebrew?). Uses m_lm_menu (clean small sample)."""
import os, sys, struct
import numpy as np

GAME = r"F:/Games/Ghost of Tsushima DC"
PSARC_DIR = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R


def get(archive, name):
    arc = R.Psarc2(os.path.join(PSARC_DIR, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def hexdump(b, base=0, n=None):
    n=len(b) if n is None else n; out=[]
    for i in range(0,min(n,len(b)),16):
        c=b[i:i+16]
        out.append(f"  {base+i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   +"".join(chr(x) if 32<=x<127 else '.' for x in c))
    return "\n".join(out)


def decode_rec(data, p, R_=64):
    r = data[p:p+R_]
    cp = struct.unpack_from("<H", r, 0)[0]
    # try many field interpretations
    u16 = struct.unpack_from("<%dH" % (R_//2), r, 0)
    f32 = struct.unpack_from("<%df" % (R_//4), r, 0)
    f16 = struct.unpack_from("<%de" % (R_//2), r, 0)
    return cp, u16, f32, f16, r


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    R_ = 64
    # find the glyph table start (cp 'A'@stride64) — from prior scan @0x42a7e
    # locate the FIRST record of the table by walking back while cp decreases by 1.
    p0 = 0x42a7e
    # walk back
    p = p0
    while p-R_ >= 0:
        cp_prev = struct.unpack_from("<H", data, p-R_)[0]
        cp_cur = struct.unpack_from("<H", data, p)[0]
        if cp_prev == cp_cur - 1 and 0x20 <= cp_prev <= 0x6ff:
            p -= R_
        else:
            break
    tbl_start = p
    # walk forward to find table end (cp stops ascending sensibly)
    q = tbl_start; cps = []
    while q+R_ <= len(data):
        cp = struct.unpack_from("<H", data, q)[0]
        if not (0x20 <= cp <= 0xffff): break
        if cps and cp <= cps[-1][1]: break  # not ascending anymore
        cps.append((q, cp)); q += R_
    print(f"== glyph table @0x{tbl_start:x} .. 0x{q:x}  ({len(cps)} records @ {R_}B) ==")
    print(f"   first cp=0x{cps[0][1]:x} ({chr(cps[0][1]) if cps[0][1]<128 else '?'}) "
          f"last cp=0x{cps[-1][1]:x} ({chr(cps[-1][1]) if cps[-1][1]<128 else '?'})")
    # codepoint coverage summary
    allcp = [c for _,c in cps]
    def rng(a,b): return sum(1 for c in allcp if a<=c<=b)
    print(f"   coverage: ASCII(0x20-0x7e)={rng(0x20,0x7e)} Latin1(0x80-0xff)={rng(0x80,0xff)} "
          f"Latin-ext(0x100-0x24f)={rng(0x100,0x24f)} Greek(0x370-0x3ff)={rng(0x370,0x3ff)} "
          f"Cyr(0x400-0x4ff)={rng(0x400,0x4ff)} Hebrew(0x5d0-0x5ea)={rng(0x5d0,0x5ea)} "
          f"Arabic(0x600-0x6ff)={rng(0x600,0x6ff)} CJK(>=0x3000)={rng(0x3000,0xffff)}")
    print(f"   min={min(allcp):#x} max={max(allcp):#x}")

    # dump header BEFORE the table (glyph count / FONTK tag?)
    print(f"\n== 96 bytes BEFORE table (header) @0x{tbl_start-96:x} ==")
    print(hexdump(data[tbl_start-96:tbl_start], tbl_start-96))
    # is glyph count == len(cps) present just before?
    for k in range(4, 64, 4):
        v = struct.unpack_from("<I", data, tbl_start-k)[0]
        if v == len(cps):
            print(f"   >>> glyph count {len(cps)} found @table-{k} (0x{tbl_start-k:x})")

    # decode a few records in detail
    print(f"\n== records A,B,C,a,0 decoded (64B) ==")
    want = {0x41,0x42,0x43,0x61,0x30}
    for q_,cp in cps:
        if cp in want:
            _,u16,f32,f16,r = decode_rec(data, q_)
            print(f"   cp=0x{cp:x}({chr(cp)}): {r.hex()}")
            print(f"      u16: {[hex(x) for x in u16]}")
            print(f"      f32: {[round(x,3) for x in f32]}")

    # Does a codepoint->index map (stride-4) or a FONTK tag sit nearby?
    for tag in (b"FONTK", b"SFontData", b"FontGlyphs", b"FontVerts", b"fOnk"):
        i = data.find(tag)
        print(f"   {tag!r} in m_lm_menu: {'@0x%x'%i if i>=0 else 'no'}")


if __name__ == "__main__":
    main()
