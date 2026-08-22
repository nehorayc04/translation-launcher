#!/usr/bin/env python3
"""scan_faces.py — measure EVERY DefineCompactedFont face in the built swf2xml dump:
its Latin cap height (the 'M' box) against its Hebrew cap height.

WHY: the death-screen "מת" renders at menu size instead of the huge DEAD headline. A face
whose Hebrew is injected SMALLER than that face's own Latin renders every Hebrew string
undersized on every surface that uses it -- and only a per-face measurement can say which
face is wrong.

⚠️ TWO SHAPES IN ONE FILE. The shipped faces are pretty-printed (a <boundingBox> spans five
lines, one <item> per line); the face we INJECTED was written with ET.tostring, so its whole
glyph array is a SINGLE ~40 MB line. A line-oriented scanner silently reports 0 for one of
the two shapes. Slurp the file and drive everything off offsets instead.

    python scan_faces.py [path/to/full.xml]
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

RE_FACE = re.compile(r'<item type="FontType"[^>]*>')
RE_NAME = re.compile(r'fontName="([^"]*)"')
RE_BBOX = re.compile(r"<boundingBox>(.*?)</boundingBox>", re.S)
RE_NUM = re.compile(r"<item>(-?\d+)</item>")
RE_CODE = re.compile(r'glyphCode="(\d+)"')

HEB_LO, HEB_HI = 0x05D0, 0x05EA


def face_slices(txt):
    """-> [(name, start, end)] over the whole document, split at each FontType item."""
    marks = [(m.start(), m.group(0)) for m in RE_FACE.finditer(txt)]
    out = []
    for i, (pos, tag) in enumerate(marks):
        nm = RE_NAME.search(tag)
        end = marks[i + 1][0] if i + 1 < len(marks) else len(txt)
        out.append((nm.group(1) if nm else "?", pos, end))
    return out


def measure(txt, a, b):
    """Within one face slice: the ordered box list from <glyphs> and the ordered code list
    from <glyphInfo>. They join by INDEX, never by proximity."""
    seg = txt[a:b]
    gs, ge = seg.find("<glyphs>"), seg.find("</glyphs>")
    is_, ie = seg.find("<glyphInfo>"), seg.find("</glyphInfo>")
    boxes, codes = [], []
    if gs >= 0 and ge > gs:
        for m in RE_BBOX.finditer(seg, gs, ge):
            n = [int(x) for x in RE_NUM.findall(m.group(1))]
            boxes.append(tuple(n[:4]) if len(n) >= 4 else None)
    if is_ >= 0 and ie > is_:
        codes = [int(x) for x in RE_CODE.findall(seg[is_:ie])]
    return boxes, codes


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    print(f"reading {path} ({os.path.getsize(path)/1e6:.0f} MB) ...", flush=True)
    with open(path, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    print(f"loaded {len(txt)/1e6:.0f} M chars\n", flush=True)

    print(f"{'face':32} {'glyphs':>7} {'M cap':>6} {'A-Z med':>8} "
          f"{'HEB n':>6} {'HEB med':>8} {'ratio':>6}")
    print("-" * 82)
    for name, a, b in face_slices(txt):
        boxes, codes = measure(txt, a, b)
        n = min(len(boxes), len(codes))
        if n == 0:
            print(f"{name[:32]:32} {'-':>7}   (boxes {len(boxes)} / codes {len(codes)})")
            continue
        lat, heb, mcap = [], [], None
        for i in range(n):
            bx, c = boxes[i], codes[i]
            if bx is None:
                continue
            h = bx[3] - bx[1]
            if c == 0x4D:
                mcap = h
            if 0x41 <= c <= 0x5A:
                lat.append(h)
            elif HEB_LO <= c <= HEB_HI:
                heb.append(h)
        lm = sorted(lat)[len(lat) // 2] if lat else 0
        hm = sorted(heb)[len(heb) // 2] if heb else 0
        ratio = (hm / lm) if lm else 0.0
        flag = ""
        if heb and lm:
            if ratio < 0.80:
                flag = "  <-- HEBREW TOO SMALL"
            elif ratio > 1.25:
                flag = "  <-- hebrew too big"
        elif lm and not heb:
            flag = "  <-- NO HEBREW AT ALL"
        print(f"{name[:32]:32} {n:>7} {str(mcap if mcap is not None else '-'):>6} {lm:>8} "
              f"{len(heb):>6} {hm:>8} {ratio:>6.2f}{flag}")


if __name__ == "__main__":
    main()
