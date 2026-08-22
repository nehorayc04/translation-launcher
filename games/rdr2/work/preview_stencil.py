#!/usr/bin/env python3
"""preview_stencil.py — render Hebrew words from the BUILT stencil font, offline.

The point is [[minimize-game-restarts]]: the death screen and the post-death menu each cost
the user a game launch to inspect, so prove the glyphs are whole from the artifact instead.
Contours are read out of the same `stencil_full.xml` the .gfx was compiled from, laid out with
each glyph's real advance, and drawn with the boundingBox overlaid — a clipped or mis-scaled
letter is then obvious in one image.

    python preview_stencil.py [word ...]      # default: מת · אבגד · שלום
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_stencil_bounds import DEFAULT, parse_codes, parse_glyphs  # noqa: E402

try:
    from PIL import Image, ImageDraw
except Exception:
    sys.exit("needs Pillow")

RE_CONTOUR = re.compile(
    r'<item type="ContourType"[^>]*?moveToX="(-?\d+)"[^>]*?moveToY="(-?\d+)"[^>]*?>')
RE_DATA = re.compile(r"<data>(.*?)</data>", re.S)
RE_ITEM = re.compile(r"<item>(-?\d+)</item>")
RE_ADV = re.compile(r'advanceX="(-?\d+)"[^>]*?glyphCode="(\d+)"')


def contours_of(chunk):
    """-> [[(x,y), ...], ...] in font units (edges are deltas from moveTo)."""
    out = []
    for cm in RE_CONTOUR.finditer(chunk):
        pen = [int(cm.group(1)), int(cm.group(2))]
        pts = [tuple(pen)]
        nxt = chunk.find('<item type="ContourType"', cm.end())
        seg = chunk[cm.end():nxt if nxt > 0 else len(chunk)]
        for dm in RE_DATA.finditer(seg):
            n = [int(x) for x in RE_ITEM.findall(dm.group(1))]
            if len(n) < 2:
                continue
            if n[0] == 0:
                pen[0] += n[1]
            elif n[0] == 1:
                pen[1] += n[1]
            elif len(n) >= 3:
                pen[0] += n[1]; pen[1] += n[2]
            pts.append(tuple(pen))
        if len(pts) > 2:
            out.append(pts)
    return out


def main():
    words = sys.argv[1:] or ["מת", "אבגד", "שלום"]
    path = DEFAULT
    if not os.path.exists(path):
        sys.exit(f"no such file: {path}")

    # chunk text per glyph, joined to the code list BY INDEX (two parallel arrays)
    MARK = '<item type="GlyphType">'
    chunks, buf, eof = [], "", False
    with open(path, encoding="utf-8", errors="replace") as f:
        while True:
            c = f.read(1 << 22)
            if not c:
                eof = True
            buf += c
            e = buf.find("</glyphs>")
            if e >= 0:
                buf, eof = buf[:e], True
            parts = buf.split(MARK)
            tail = "" if eof else parts.pop()
            for p in parts:
                if "<boundingBox" in p:
                    chunks.append(p)
            buf = tail
            if eof:
                break
    codes = parse_codes(path)
    boxes = [b for b, _i in parse_glyphs(path)]
    by_code = {c: (chunks[i], boxes[i]) for i, c in enumerate(codes) if i < len(chunks)}

    adv = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        inside = False
        for line in f:
            if "<glyphInfo>" in line:
                inside = True
            elif "</glyphInfo>" in line:
                break
            elif inside:
                for a, c in RE_ADV.findall(line):
                    adv[int(c)] = int(a)

    SCALE = 0.85
    PAD = 40
    for w in words:
        # RTL: the leftmost drawn glyph is the LAST letter, which is how the engine stores it
        letters = list(reversed(w))
        total = sum(adv.get(ord(ch), 140) for ch in letters)
        W = int(total * SCALE) + PAD * 2
        H = int(260 * SCALE) + PAD * 2 + 40
        img = Image.new("RGB", (max(W, 200), H), (16, 14, 12))
        d = ImageDraw.Draw(img)
        x = PAD
        base = H - PAD - 20
        for ch in letters:
            ent = by_code.get(ord(ch))
            if not ent:
                x += int(adv.get(ord(ch), 140) * SCALE)
                continue
            chunk, box = ent
            for cont in contours_of(chunk):
                pts = [(x + p[0] * SCALE, base + p[1] * SCALE) for p in cont]
                if len(pts) > 2:
                    d.polygon(pts, fill=(236, 228, 214))
            if box:
                d.rectangle([x + box[0] * SCALE, base + box[1] * SCALE,
                             x + box[2] * SCALE, base + box[3] * SCALE],
                            outline=(190, 60, 40))
            x += int(adv.get(ord(ch), 140) * SCALE)
        out = os.path.join(os.path.dirname(path), f"preview_{w}.png")
        img.save(out)
        print("wrote", out, img.size)


if __name__ == "__main__":
    main()
