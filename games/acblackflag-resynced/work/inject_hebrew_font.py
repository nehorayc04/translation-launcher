#!/usr/bin/env python3
"""
THE FIX for Hebrew in the ARABIC slot.

Root cause (measured, not guessed): the Arabic locale loads **Noto Kufi Arabic**
(PhoenixFont fileIDs 0xb4c3f12b Light / 0xb4c3f12c ExtraLight), which contains
**ZERO Hebrew codepoints**. Every other locale loads Avenir Next World, which ships
all 27 Hebrew letters. That is the entire tofu explanation — not bidi, not shaping,
not the glyph atlas.

Fix: copy the Hebrew glyphs out of Avenir Next World (same UPM=1000, same TrueType
`glyf` outlines, cap height 708 vs Noto's 714 = 0.8% apart, so a 1:1 copy is
metrically correct) into Noto Kufi Arabic, and re-embed the patched fonts through
the already-solved patch_02 override.

Resource layout (reverse-engineered + verified on 4 fonts):
    record = CFD0(20 bytes) + CFD1(obj)
    CFD0@10                = len(obj)
    obj  = [header][sfnt][trailer]
    obj@0                  = class hash 0xa6ea7232 (PhoenixFont)
    obj@4                  = 17 + sfntLen + trailerLen      <- objectSize
    obj@(sfntOff-4)        = sfntLen + trailerLen           <- payload length
    (both must be re-derived when the font grows)

    python work/inject_hebrew_font.py            # build patched fonts -> work/hefonts/
    python work/inject_hebrew_font.py --verify   # report coverage of the built fonts
"""
import io
import os
import struct
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
FONTSYS = os.path.join(HERE, "fontsys")
OUT = os.path.join(HERE, "hefonts")

SFNT_MAGICS = (b"\x00\x01\x00\x00", b"OTTO", b"true")

# target (Arabic slot)                 <- donor (same weight)
PAIRS = [
    ("PhoenixFont_7374_b4c3f12b.bin", "PhoenixFont_7378_6b3a9ee0.bin", 0xB4C3F12B, "NotoKufi Light  <- Avenir Regular"),
    ("PhoenixFont_7383_b4c3f12c.bin", "PhoenixFont_7384_6b3a9edf.bin", 0xB4C3F12C, "NotoKufi XLight <- Avenir Light"),
]

HEB_RANGE = range(0x0590, 0x0600)          # full Hebrew block (letters + niqqud + punctuation)


def sfnt_span(obj):
    """Return (offset, length) of the embedded sfnt inside the resource object."""
    offs = [obj.find(m) for m in SFNT_MAGICS if 0 <= obj.find(m) < 4096]
    off = min(offs)
    n = struct.unpack_from(">H", obj, off + 4)[0]
    end = 0
    for i in range(n):
        p = off + 12 + i * 16
        o = struct.unpack_from(">I", obj, p + 8)[0]
        l = struct.unpack_from(">I", obj, p + 12)[0]
        end = max(end, o + l)
    return off, end


def load_resource(path):
    """-> (cfd0, obj, sfntOff, sfntLen, trailerLen)"""
    d = open(path, "rb").read()
    cfd0, obj = d[:20], d[20:]
    off, ln = sfnt_span(obj)
    return cfd0, obj, off, ln, len(obj) - (off + ln)


def copy_hebrew(target_sfnt, donor_sfnt):
    """Copy every Hebrew-block glyph from donor into target. Returns (font, added)."""
    from fontTools.ttLib import TTFont

    tgt = TTFont(io.BytesIO(target_sfnt))
    don = TTFont(io.BytesIO(donor_sfnt))
    tcmap, dcmap = tgt.getBestCmap(), don.getBestCmap()
    tglyf, dglyf = tgt["glyf"], don["glyf"]
    thmtx, dhmtx = tgt["hmtx"], don["hmtx"]

    # donor glyphs to bring over (plus any composite components they reference)
    wanted = {cp: dcmap[cp] for cp in HEB_RANGE if cp in dcmap}
    needed = set(wanted.values())
    frontier = list(needed)
    while frontier:
        gn = frontier.pop()
        g = dglyf[gn]
        if g.isComposite():
            for comp in g.components:
                if comp.glyphName not in needed:
                    needed.add(comp.glyphName); frontier.append(comp.glyphName)

    # NB: tgt.getGlyphOrder() and tgt["glyf"].glyphOrder are the SAME list object, and
    # glyf.__setitem__ already appends to it — so never append manually (double-append
    # desyncs len(glyphOrder) from len(glyphs) and maxp.recalc asserts).
    rename = {}
    taken = set(tgt.getGlyphOrder())
    for gn in sorted(needed):
        new = gn
        while new in taken:
            new = f"he_{new}"
        rename[gn] = new
        taken.add(new)

    # insert glyphs (outlines + advance widths)
    for gn in sorted(needed):
        new = rename[gn]
        g = dglyf[gn]
        if g.isComposite():                      # repoint component names
            g = g.__class__.__new__(g.__class__)
            g.__dict__.update(dglyf[gn].__dict__)
            import copy as _c
            g.components = _c.deepcopy(dglyf[gn].components)
            for comp in g.components:
                comp.glyphName = rename.get(comp.glyphName, comp.glyphName)
        tglyf[new] = g                  # also appends `new` to the shared glyphOrder
        thmtx[new] = dhmtx[gn]
    tgt["maxp"].numGlyphs = len(tgt.getGlyphOrder())

    # map the Hebrew codepoints in every unicode cmap subtable
    added = 0
    for sub in tgt["cmap"].tables:
        if not sub.isUnicode():
            continue
        for cp, gn in wanted.items():
            sub.cmap[cp] = rename[gn]
            added += 1
    return tgt, len(wanted), added


def rebuild_resource(cfd0, obj, sfnt_off, old_sfnt_len, trailer_len, new_sfnt):
    """Splice the new sfnt in and re-derive every length field."""
    header = obj[:sfnt_off]
    trailer = obj[sfnt_off + old_sfnt_len:]
    assert len(trailer) == trailer_len
    new_obj = bytearray(header + new_sfnt + trailer)
    payload = len(new_sfnt) + trailer_len
    struct.pack_into("<I", new_obj, 4, 17 + payload)              # objectSize
    struct.pack_into("<I", new_obj, sfnt_off - 4, payload)        # payload length
    new_cfd0 = bytearray(cfd0)
    struct.pack_into("<I", new_cfd0, 10, len(new_obj))            # decoded length of CFD1
    return bytes(new_cfd0), bytes(new_obj)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if a.verify:
        from fontTools.ttLib import TTFont
        for _, _, fid, label in PAIRS:
            p = os.path.join(OUT, f"{fid:08x}.bin")
            if not os.path.isfile(p):
                print(f"{label}: not built"); continue
            cfd0, obj, off, ln, tl = load_resource(p)
            f = TTFont(io.BytesIO(obj[off:off + ln]), lazy=True)
            cm = f.getBestCmap()
            letters = sum(1 for c in range(0x05D0, 0x05EB) if c in cm)
            block = sum(1 for c in HEB_RANGE if c in cm)
            ar = sum(1 for c in range(0x0600, 0x0700) if c in cm)
            print(f"{label}: Hebrew letters {letters}/27, block {block}, Arabic {ar} (obj {len(obj):,} B)")
            f.close()
        return 0

    for tgt_file, don_file, fid, label in PAIRS:
        cfd0, obj, off, ln, tl = load_resource(os.path.join(FONTSYS, tgt_file))
        _, dobj, doff, dln, _ = load_resource(os.path.join(FONTSYS, don_file))
        font, n_cp, n_map = copy_hebrew(obj[off:off + ln], dobj[doff:doff + dln])
        buf = io.BytesIO(); font.save(buf); new_sfnt = buf.getvalue(); font.close()
        new_cfd0, new_obj = rebuild_resource(cfd0, obj, off, ln, tl, new_sfnt)
        open(os.path.join(OUT, f"{fid:08x}.bin"), "wb").write(new_cfd0 + new_obj)
        print(f"{label}")
        print(f"   copied {n_cp} Hebrew codepoints ({n_map} cmap entries)")
        print(f"   sfnt {ln:,} -> {len(new_sfnt):,} B   obj {len(obj):,} -> {len(new_obj):,} B "
              f"(+{len(new_obj)-len(obj):,})")
        print(f"   obj@4={struct.unpack_from('<I', new_obj, 4)[0]:,}  "
              f"payload@{off-4}={struct.unpack_from('<I', new_obj, off-4)[0]:,}  "
              f"CFD0@10={struct.unpack_from('<I', new_cfd0, 10)[0]:,}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
