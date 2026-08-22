"""Rasterise a tessellated glyph set to a PNG — the only argument-ending test.

Left half: the triangles we would emit.  Right half: an independent reference
raster produced by winding-number point sampling of the raw outline.  If the two
agree the tessellation is correct; the difference image shows exactly where not.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_glyphgen as G                                            # noqa: E402
from PIL import Image, ImageDraw                                    # noqa: E402

HEEBO = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo")
OUT = os.path.join(HERE, "..", "extract")
CELL, PAD = 120, 8


def raster_tris(verts, tris, box, size):
    im = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    sc = (size - 2 * PAD) / max(x1 - x0, y1 - y0, 1e-6)

    def T(p):
        return (PAD + (p[0] - x0) * sc, size - PAD - (p[1] - y0) * sc)
    for i in range(0, len(tris), 3):
        d.polygon([T(verts[tris[i]]), T(verts[tris[i + 1]]), T(verts[tris[i + 2]])],
                  fill=255)
    return im


def raster_winding(contours, box, size):
    """Reference: winding number by ray casting, sampled per pixel centre."""
    im = Image.new("L", (size, size), 0)
    px = im.load()
    x0, y0, x1, y1 = box
    sc = (size - 2 * PAD) / max(x1 - x0, y1 - y0, 1e-6)
    segs = []
    for c in contours:
        for i in range(len(c)):
            a, b = c[i], c[(i + 1) % len(c)]
            if a[1] != b[1]:
                segs.append((a, b))
    for py in range(size):
        wy = (size - PAD - py - 0.5) / sc + y0
        xs = []
        for a, b in segs:
            if (a[1] <= wy < b[1]) or (b[1] <= wy < a[1]):
                t = (wy - a[1]) / (b[1] - a[1])
                xs.append((a[0] + (b[0] - a[0]) * t, 1 if b[1] > a[1] else -1))
        if not xs:
            continue
        xs.sort()
        w, start = 0, None
        for x, d_ in xs:
            prev = w
            w += d_
            if prev == 0 and w != 0:
                start = x
            elif prev != 0 and w == 0 and start is not None:
                a_ = int(PAD + (start - x0) * sc + 0.5)
                b_ = int(PAD + (x - x0) * sc + 0.5)
                for pxx in range(max(0, a_), min(size, b_)):
                    px[pxx, py] = 255
                start = None
    return im


def main():
    weight = sys.argv[1] if len(sys.argv) > 1 else "Medium"
    text = sys.argv[2] if len(sys.argv) > 2 else "אבגדהוזחטיכךלמםנןסעפףצץקרשתHAOצ"
    d = G.Donor(os.path.join(HEEBO, f"Heebo-{weight}.ttf"))
    body = d.ink(ord("ה"), 1.0)[3]
    s = 0.60 / body

    cols = min(len(text), 14)
    rows = (len(text) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * CELL, rows * CELL * 2), (16, 16, 22))
    worst = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if not d.has(cp):
            continue
        cs = d.outline(cp, s)
        v, t = G.tessellate(cs)
        xs = [p[0] for c in cs for p in c]
        ys = [p[1] for c in cs for p in c]
        box = (min(xs), min(ys), max(xs), max(ys))
        a = raster_tris(v, t, box, CELL)
        b = raster_winding(cs, box, CELL)
        diff = sum(1 for pa, pb in zip(a.getdata(), b.getdata()) if pa != pb)
        ink = sum(1 for pb in b.getdata() if pb)
        worst.append((diff / max(ink, 1), ch, len(v), len(t) // 3))
        cx, cy = (i % cols) * CELL, (i // cols) * CELL * 2
        sheet.paste(Image.merge("RGB", (a, a, a)), (cx, cy))
        sheet.paste(Image.merge("RGB", (b, b, b)), (cx, cy + CELL))
    p = os.path.join(OUT, f"glyph_check_{weight}.png")
    sheet.save(p)
    worst.sort(reverse=True)
    print(f"{p}   (top row = our triangles, bottom = reference)")
    print(f"  scale {s:.4f}  body {body:.4f}")
    print("  worst mismatch vs reference raster (fraction of ink pixels):")
    for f_, ch, nv, nt in worst[:8]:
        print(f"    {ch}  {f_*100:6.2f}%   V={nv:4d} T={nt:4d}")
    print(f"  median {sorted(w[0] for w in worst)[len(worst)//2]*100:.2f}%")


main()
