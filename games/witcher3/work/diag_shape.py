#!/usr/bin/env python3
"""Decode an ORIGINAL Arial Hebrew glyph shape from fonts_ar.redswf and compare it, structurally,
to the David glyph my encoder generates for the same codepoint. The original is the ground truth
for the fill-style/winding convention Scaleform here expects."""
import os, struct, zlib
import potato_bundle as P
import gfx_inspect as G
import swf_font as S
import swf_glyphgen as GG
from fontTools.ttLib import TTFont

GAME = r"D:\Games\The Witcher 3 - Complete Edition"
DAVID = r"C:\Windows\Fonts\david.ttf"
SWF_EM = 20480
CP = 0x05D0  # 'א'


class BR:
    def __init__(s, d, byte=0, bit=0): s.d = d; s.byte = byte; s.bit = bit
    def u(s, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((s.d[s.byte] >> (7 - s.bit)) & 1)
            s.bit += 1
            if s.bit == 8: s.bit = 0; s.byte += 1
        return v
    def sb(s, n):
        v = s.u(n)
        if n and (v >> (n - 1)): v -= (1 << n)
        return v


def decode_shape(shape, nfb_expected=None):
    """Decode a glyph SHAPE (starts with NumFillBits/NumLineBits). Return a list of readable ops."""
    br = BR(shape)
    nfb = br.u(4); nlb = br.u(4)
    ops = [f"NumFillBits={nfb} NumLineBits={nlb}"]
    guard = 0
    while True:
        guard += 1
        if guard > 4000: ops.append("...RUNAWAY"); break
        edge = br.u(1)
        if not edge:
            flags = br.u(5)
            if flags == 0:
                ops.append("END"); break
            newstyles = (flags >> 4) & 1
            linestyle = (flags >> 3) & 1
            fs1 = (flags >> 2) & 1
            fs0 = (flags >> 1) & 1
            moveto = flags & 1
            parts = []
            if moveto:
                mb = br.u(5); mx = br.sb(mb); my = br.sb(mb)
                parts.append(f"MoveTo({mx},{my}) mb={mb}")
            if fs0: parts.append(f"FillStyle0={br.u(nfb)}")
            if fs1: parts.append(f"FillStyle1={br.u(nfb)}")
            if linestyle: parts.append(f"LineStyle={br.u(nlb)}")
            if newstyles: parts.append("NEWSTYLES!")
            ops.append("STYLE " + " ".join(parts))
        else:
            straight = br.u(1)
            nb = br.u(4) + 2
            if straight:
                general = br.u(1)
                if general:
                    dx = br.sb(nb); dy = br.sb(nb)
                    ops.append(f"line({dx},{dy})")
                else:
                    vert = br.u(1)
                    d = br.sb(nb)
                    ops.append(f"lineV({d})" if vert else f"lineH({d})")
            else:
                cdx = br.sb(nb); cdy = br.sb(nb); adx = br.sb(nb); ady = br.sb(nb)
                ops.append(f"curve c({cdx},{cdy}) a({adx},{ady})")
    return ops, br.byte, len(shape)


def main():
    bundle = os.path.join(GAME, "content", "content0", "bundles", "r4gui.bundle")
    d, ents = P.list_entries(bundle)
    e = [x for x in ents if x["name"].endswith("fonts_ar.redswf")][0]
    redswf = P.extract(d, e)
    gfx, ver, uncomp = G.decompress_gfx(redswf)
    tags = G.list_tags(gfx)
    # font id=1 = Arial with Hebrew
    target = None
    for code, length, off in tags:
        if code == 75:
            f = S.parse_definefont3(gfx[off:off + length])
            if CP in f["codes"]:
                target = f; break
    assert target, "no font covers the codepoint"
    i = target["codes"].index(CP)
    orig = target["shapes"][i]
    print(f"=== ORIGINAL font id={target['font_id']} name={target['name'][:-1].decode()!r} "
          f"glyph[{i}] U+{CP:04X}  {len(orig)} bytes ===")
    print("  hex:", orig.hex())
    ops, consumed, total = decode_shape(orig)
    for o in ops: print("   ", o)
    print(f"  consumed {consumed}/{total} bytes")
    if target["has_layout"]:
        print(f"  advance={target['layout']['advance'][i]}  bounds={target['layout']['bounds'][i].hex()}")

    print()
    t = TTFont(DAVID); scale = SWF_EM / t["head"].unitsPerEm
    gs = t.getGlyphSet(); cmap = t.getBestCmap()
    gname = cmap[CP]
    mine = GG.glyph_to_shape(gs, gname, scale, y_sign=-1)
    print(f"=== MINE (David glyph {gname!r} scale={scale})  {len(mine)} bytes ===")
    print("  hex:", mine.hex())
    ops, consumed, total = decode_shape(mine)
    for o in ops[:60]: print("   ", o)
    if len(ops) > 60: print(f"    ... (+{len(ops)-60} more)")
    print(f"  consumed {consumed}/{total} bytes")
    print(f"  David advance raw={gs[gname].width} -> scaled={round(gs[gname].width*scale)}")


if __name__ == "__main__":
    main()
