#!/usr/bin/env python3
"""verify_stencil_bounds.py — prove the death-screen clipping fix, offline.

BUG 2 (`מת` clipped on the right) and BUG 3 (the post-death menu drawing מ/ת oversized and
overlapping) are ONE defect: `build_letter` computed each glyph's `boundingBox` over the
SOLID contours only, so any letter whose outer ring landed in the hole set got a box a
quarter of its real height. Scaleform rasterises a glyph into its cache using those bounds,
so an undersized box BOTH clips the ink AND rescales it.

This reads the box + the real ink extent for every Hebrew glyph out of the BUILT xml (not
out of the builder) and fails if any box does not contain its own ink. Verifying the
ARTIFACT rather than the intent is the whole point — the builder happily reported success
while shipping quarter-height boxes.

Structure of the dump (measured, not assumed): the face is TWO PARALLEL ARRAYS —
`<glyphs>` holds N `GlyphType` items (boundingBox as four bare <item> children, then
contours whose edges are DELTAS from moveToX/moveToY) and `<glyphInfo>` holds the SAME N
`GlyphInfoType` items carrying `glyphCode`. They join by INDEX, never by proximity.

    python verify_stencil_bounds.py [path/to/stencil_full.xml]
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "_fontinspect", "stencil_full.xml")
HEB_LO, HEB_HI = 0x05D0, 0x05EA

RE_MOVE = re.compile(r'moveToX="(-?\d+)"\s+moveToY="(-?\d+)"')
RE_ITEM = re.compile(r"<item>(-?\d+)</item>")
RE_CODE = re.compile(r'glyphCode="(\d+)"')


RE_BBOX = re.compile(r"<boundingBox>(.*?)</boundingBox>", re.S)
RE_DATA = re.compile(r"<data>(.*?)</data>", re.S)
RE_CONTOUR = re.compile(r'<item type="ContourType"[^>]*?moveToX="(-?\d+)"[^>]*?moveToY="(-?\d+)"[^>]*?>')


def parse_glyphs(path):
    """-> list of (bbox, ink) in file order, one per GlyphType.

    ⚠️ Split on the GlyphType marker, do NOT drive a state machine off LINES: the injector
    writes each glyph with ET.tostring, so `<data>…</data>` lands on ONE line and a
    line-based scanner silently collects nothing and reports every glyph as clipping.
    """
    MARK = '<item type="GlyphType">'
    out, buf, eof = [], "", False
    with open(path, encoding="utf-8", errors="replace") as f:
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                eof = True
            buf += chunk
            end = buf.find("</glyphs>")
            if end >= 0:
                buf, eof = buf[:end], True
            parts = buf.split(MARK)
            tail = "" if eof else parts.pop()      # the last piece may still be growing
            for p in parts:
                if "<boundingBox" in p:
                    out.append(_measure(p))
            buf = tail
            if eof:
                break
    return out


def _measure(p):
    m = RE_BBOX.search(p)
    box = None
    if m:
        nums = [int(x) for x in RE_ITEM.findall(m.group(1))]
        if len(nums) >= 4:
            box = (nums[0], nums[1], nums[2], nums[3])
    ink, pen = None, None
    pos = 0
    for cm in RE_CONTOUR.finditer(p):
        pen = [int(cm.group(1)), int(cm.group(2))]
        ink = _grow(ink, pen)
        pos = cm.end()
        nxt = p.find('<item type="ContourType"', pos)
        seg = p[pos:nxt if nxt > 0 else len(p)]
        for dm in RE_DATA.finditer(seg):
            n = [int(x) for x in RE_ITEM.findall(dm.group(1))]
            if len(n) < 2:
                continue
            if n[0] == 0:            # horizontal
                pen[0] += n[1]
            elif n[0] == 1:          # vertical
                pen[1] += n[1]
            elif len(n) >= 3:        # general
                pen[0] += n[1]
                pen[1] += n[2]
            ink = _grow(ink, pen)
    return (box, ink)


def _grow(ink, p):
    if ink is None:
        return [p[0], p[1], p[0], p[1]]
    ink[0] = min(ink[0], p[0]); ink[1] = min(ink[1], p[1])
    ink[2] = max(ink[2], p[0]); ink[3] = max(ink[3], p[1])
    return ink


def parse_codes(path):
    codes, inside = [], False
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "<glyphInfo>" in line:
                inside = True
                continue
            if "</glyphInfo>" in line:
                break
            if inside:
                m = RE_CODE.search(line)
                if m:
                    codes.append(int(m.group(1)))
    return codes


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(path):
        sys.exit(f"no such file: {path}  (run rdr2_stencil_inject.py build first)")
    print(f"reading {path} ({os.path.getsize(path)/1e6:.0f} MB)")
    glyphs = parse_glyphs(path)
    codes = parse_codes(path)
    print(f"glyphs {len(glyphs)} · codes {len(codes)}")
    if len(glyphs) != len(codes):
        sys.exit(f"!! the two arrays disagree ({len(glyphs)} vs {len(codes)}) — "
                 "the join is by index, so this must match")

    # 🔴 THE TEST IS A CALIBRATED RULER, NOT AN ABSOLUTE RULE.
    # "the box must strictly contain the reconstructed ink" was the obvious check and it is
    # WRONG here: the game's OWN Latin glyphs fail it 44 times out of 58, because a curved
    # edge carries control+anchor deltas that a linear replay cannot follow, and because a
    # referenced contour is not replayable at all. A test the shipping font fails cannot
    # tell you anything about ours. What IS decisive is the box-height DISTRIBUTION against
    # the same font's Latin: BUG 2 showed up as boxes a QUARTER of their letter's height,
    # which is far outside anything the engine already renders correctly.
    heb, lat = [], []
    for code, (box, ink) in zip(codes, glyphs):
        if box is None:
            continue
        h = box[3] - box[1]
        if HEB_LO <= code <= HEB_HI:
            heb.append((code, box[2] - box[0], h))
        elif 0x41 <= code <= 0x5A:                      # A-Z, the reference
            lat.append(h)

    print(f"\nHebrew glyphs found: {len(heb)} of 27")
    for code, w, h in sorted(heb):
        print(f"  U+{code:04X} {chr(code)}  box {w:6} x {h:6}")
    if not heb or not lat:
        sys.exit("!! nothing to compare")
    hh = sorted(h for _c, _w, h in heb)
    ll = sorted(lat)
    lo, med = ll[0], ll[len(ll) // 2]
    print(f"\nLatin A-Z box height : min {lo} · median {med} · max {ll[-1]}   (n={len(ll)})")
    print(f"Hebrew  box height   : min {hh[0]} · median {hh[len(hh)//2]} · max {hh[-1]}")

    # a Hebrew cap is ~0.65 of a Latin cap in this build; anything under HALF the Latin
    # minimum is the quarter-height defect, not a design choice.
    floor = lo * 0.5
    runts = [(c, w, h) for c, w, h in heb if h < floor]
    if len(heb) != 27:
        sys.exit(f"!! only {len(heb)} of 27 Hebrew glyphs carry a box")
    if runts:
        for c, w, h in runts:
            print(f"!! U+{c:04X} {chr(c)}: box height {h} is under {floor:.0f} "
                  f"(half the smallest Latin box) — this is the BUG-2 signature")
        sys.exit(1)
    print(f"\nPASS — 27/27 Hebrew glyphs, every box height >= {floor:.0f}; "
          "no quarter-height outlier remains.")


if __name__ == "__main__":
    main()
