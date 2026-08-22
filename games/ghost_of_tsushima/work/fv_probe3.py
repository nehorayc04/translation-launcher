#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fv_probe3.py — dump the FULL 64-byte records of m_lm_menu's glyph list in cp order,
decoding every plausible sub-field, and test whether +12/+14/+16/+18 form a
(firstVert,count) reference that tiles a buffer. Also gathers the 24-byte 'geometry'
blocks and checks the (offset?,count?) tiling hypothesis across distinct blocks."""
import os, sys, struct
GAME = r"F:/Games/Ghost of Tsushima DC"
PD = os.path.join(GAME, "cache_pc", "psarc")
sys.path.insert(0, r"C:/Users/Nehoray_Cohen/Projects/Game translator/games/tlou2/tools")
import dsar as R

GREC = 64


def get(archive, name):
    arc = R.Psarc2(os.path.join(PD, archive))
    tgt = next((e for e in arc.files() if e.path.rstrip("/").endswith(name)), None)
    data = arc.extract(tgt) if tgt else None
    arc.d.f.close()
    return data


def all_records(data, first=0x41abe, last=0x44000):
    """Walk 64-byte records from `first` while +8==4 (rich-ish); return (off,cp,rec)."""
    out = []
    q = first
    while q + GREC <= last:
        c8 = struct.unpack_from("<I", data, q + 8)[0]
        cp = struct.unpack_from("<H", data, q)[0]
        if c8 != 4:
            break
        out.append((q, cp, data[q:q + GREC]))
        q += GREC
    return out


def main():
    data = get("gapack_misc_m.psarc", "m_lm_menu.sprig.xpps")
    recs = all_records(data)
    print(f"walked {len(recs)} contiguous 64-byte records @0x{recs[0][0]:x}..0x{recs[-1][0]+GREC:x}")
    print(f"cp sequence: {[hex(c) for _,c,_ in recs][:40]}...")

    # decode every record's low-cardinality fields
    print("\n cp     +4(metric)  +12u32     +14u8 +16u16 +18u16 +20u16 | 24Bgeom(first8 hex)")
    for off, cp, r in recs:
        metric = struct.unpack_from("<f", r, 4)[0]
        f12 = struct.unpack_from("<I", r, 12)[0]
        b14 = r[14]
        h16 = struct.unpack_from("<H", r, 16)[0]
        h18 = struct.unpack_from("<H", r, 18)[0]
        h20 = struct.unpack_from("<H", r, 20)[0]
        geo8 = r[22:30].hex()
        ch = chr(cp) if 32 <= cp < 127 else f"({cp:#x})"
        print(f" {ch:>6} {metric:9.4f}  0x{f12:08x} {b14:3d}  0x{h16:04x} 0x{h18:04x} 0x{h20:04x} | {geo8}")

    # Hypothesis A: +16 low u16 = a count or index (non-0xffff ones)
    print("\n== records where +16 != 0xffff (a 'real' reference?) ==")
    for off, cp, r in recs:
        h16 = struct.unpack_from("<H", r, 16)[0]
        if h16 != 0xffff:
            ch = chr(cp) if 32 <= cp < 127 else f"({cp:#x})"
            print(f"  {ch:>6} cp=0x{cp:x}  +16=0x{h16:04x}  +14={r[14]}  metric={struct.unpack_from('<f',r,4)[0]:.3f}")

    # Hypothesis B: the 24-byte geometry is [hash/ref]. Gather distinct blocks + count glyphs.
    from collections import defaultdict
    geo = defaultdict(list)
    for off, cp, r in recs:
        geo[bytes(r[22:46])].append(cp)
    print(f"\n== {len(recs)} records -> {len(geo)} distinct 24-byte geometry blocks ==")
    # is there a 4-byte column within the 24 that is a plausible ascending offset across distinct blocks?
    blocks = list(geo.keys())
    for pos in range(0, 24 - 3):
        vals = [struct.unpack_from("<I", b, pos)[0] for b in blocks]
        uniq = len(set(vals))
        small = sum(1 for v in vals if v < len(data))
        aligned = sum(1 for v in vals if v % 4 == 0)
        if small >= len(vals) * 0.7:
            sv = sorted(vals)
            print(f"  block+{pos}: uniq={uniq}/{len(vals)} in-file={small} 4aligned={aligned} "
                  f"range[{sv[0]}..{sv[-1]}] sample={sv[:6]}")


if __name__ == "__main__":
    main()
