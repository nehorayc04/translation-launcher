#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe1.py — locate the FontVerts buffer for m_lm_menu's Latin glyph table.

Steps (all verified against the real file, no game-file writes):
  1. byte-column constancy across the 103 glyph records (find field boundaries the
     word-table analysis blurred).
  2. dump the KCAP header + the @0x2c trailer directory (section table).
  3. dump raw bytes immediately BEFORE and AFTER the glyph table to see what
     section precedes/follows (a vertex buffer would be a big float/int region).
"""
import os, sys, struct
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tlou2", "tools"))
import dsar as R

GREC = 64
TBL = 0x4223e


def get(archive, name):
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def hexdump(b, base=0):
    out = []
    for i in range(0, len(b), 16):
        c = b[i:i + 16]
        out.append(f"  {base+i:08x}  {' '.join(f'{x:02x}' for x in c):<47}  "
                   + "".join(chr(x) if 32 <= x < 127 else '.' for x in c))
    return "\n".join(out)


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    print(f"file size = {len(data):,}  magic={data[:4]!r}")
    # KCAP header
    print("\n== KCAP header (0x00..0x40) ==")
    print(hexdump(data[:0x40], 0))
    base = struct.unpack_from("<I", data, 0x28)[0]
    trailer = struct.unpack_from("<I", data, 0x2c)[0]
    print(f"\n  base(@0x28)=0x{base:x}({base})  trailer(@0x2c)=0x{trailer:x}({trailer})")

    # trailer directory
    print(f"\n== trailer directory @0x{trailer:x} ==")
    print(hexdump(data[trailer:trailer + 0x100], trailer))

    # read the glyph table
    recs = []
    q = TBL
    while q + GREC <= len(data):
        cp = struct.unpack_from("<H", data, q)[0]
        recs.append((cp, data[q:q + GREC]))
        if cp == 0xffff:
            break
        q += GREC
    tbl_end = q + GREC if recs and recs[-1][0] == 0xffff else q
    body = [r for cp, r in recs if cp != 0xffff]
    print(f"\n== glyph table @0x{TBL:x}..0x{tbl_end:x}  ({len(recs)} recs, {len(body)} glyphs) ==")

    # byte-column constancy
    print("\n== byte-column constancy across 103 glyph records ==")
    consts = []
    varies = []
    for off in range(GREC):
        vals = set(r[off] for r in body)
        if len(vals) == 1:
            consts.append((off, next(iter(vals))))
        else:
            varies.append((off, len(vals)))
    print("  CONSTANT byte columns:")
    line = ""
    for off, v in consts:
        line += f"+{off}=0x{v:02x} "
    print("   ", line)
    print("  VARYING byte columns (off:distinct):")
    print("   ", " ".join(f"+{off}:{n}" for off, n in varies))

    # look for a monotonic / offset-like u32 within record, scanning ALL byte offsets 0..60
    print("\n== per-record u32 at every byte offset — flag monotonic-ascending in cp order ==")
    for off in range(0, GREC - 3):
        col = [struct.unpack_from("<I", r, off)[0] for r in body]
        mono = all(col[i] <= col[i + 1] for i in range(len(col) - 1))
        strict = all(col[i] < col[i + 1] for i in range(len(col) - 1))
        if mono:
            print(f"  +{off}: MONOTONIC{'(strict)' if strict else ''} sample={col[:6]}..{col[-3:]}")

    # dump 64 bytes BEFORE the table (section header) and 128 AFTER (next section)
    print(f"\n== 128 bytes BEFORE table @0x{TBL-128:x} ==")
    print(hexdump(data[TBL - 128:TBL], TBL - 128))
    print(f"\n== 128 bytes AFTER table @0x{tbl_end:x} ==")
    print(hexdump(data[tbl_end:tbl_end + 128], tbl_end))


if __name__ == "__main__":
    main()
