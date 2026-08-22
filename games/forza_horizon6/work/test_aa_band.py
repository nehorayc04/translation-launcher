"""Validate the anti-aliasing band before it ever reaches the game.

Two independent checks per glyph:

1. GEOMETRY — the region the shader treats as covered (`cv >= 0`, i.e. interior
   plus the inner half of every band quad) must reproduce the TRUE outline. If
   the band is mis-placed the glyph silently gets fatter or thinner.
2. COVERAGE — simulate the engine's analytic AA (`alpha = cv / fwidth(cv) + 0.5`)
   and render it, so the edge quality is judged from an image rather than a launch.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_glyphgen as G                                            # noqa: E402
import numpy as np                                                  # noqa: E402
from PIL import Image                                               # noqa: E402

HEEBO = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo")
HEB = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"


def raster(verts, tris, box, size, mode):
    """mode='cov' -> analytic AA alpha;  mode='bin' -> the cv>=0 region."""
    x0, y0, x1, y1 = box
    sc = (size - 16) / max(x1 - x0, y1 - y0, 1e-9)
    img = np.zeros((size, size), np.float32)

    def T(p):
        return (8 + (p[0] - x0) * sc, size - 8 - (p[1] - y0) * sc)

    for i in range(0, len(tris), 3):
        P = [verts[tris[i + k]] for k in range(3)]
        S = [T(p) for p in P]
        cv = [p[3] for p in P]
        xs = [s[0] for s in S]; ys = [s[1] for s in S]
        lo_x, hi_x = int(max(0, min(xs))), int(min(size - 1, max(xs) + 1))
        lo_y, hi_y = int(max(0, min(ys))), int(min(size - 1, max(ys) + 1))
        if hi_x < lo_x or hi_y < lo_y:
            continue
        (ax, ay), (bx, by), (cx, cy) = S
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        yy, xx = np.mgrid[lo_y:hi_y + 1, lo_x:hi_x + 1]
        px, py = xx + 0.5, yy + 0.5
        l1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
        l2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if not inside.any():
            continue
        val = l1 * cv[0] + l2 * cv[1] + l3 * cv[2]
        if mode == "bin":
            a = (val >= 0).astype(np.float32)
        else:
            # fwidth of a linearly-interpolated attribute is constant per triangle
            gx = ((by - cy) * cv[0] + (cy - ay) * cv[1] + (ay - by) * cv[2]) / den
            gy = ((cx - bx) * cv[0] + (ax - cx) * cv[1] + (bx - ax) * cv[2]) / den
            fw = abs(gx) + abs(gy)
            a = np.clip(val / fw + 0.5, 0, 1) if fw > 1e-9 else np.ones_like(val)
        sub = img[lo_y:hi_y + 1, lo_x:hi_x + 1]
        np.maximum(sub, np.where(inside, a, 0), out=sub)
    return img


def reference(contours, box, size):
    """Winding-number truth for the TRUE outline, supersampled."""
    x0, y0, x1, y1 = box
    sc = (size - 16) / max(x1 - x0, y1 - y0, 1e-9)
    img = np.zeros((size, size), np.float32)
    segs = [(a, b) for c in contours for a, b in zip(c, c[1:] + c[:1]) if a[1] != b[1]]
    for py in range(size):
        wy = (size - 8 - py - 0.5) / sc + y0
        xs = sorted((a[0] + (b[0] - a[0]) * (wy - a[1]) / (b[1] - a[1]),
                     1 if b[1] > a[1] else -1)
                    for a, b in segs if (a[1] <= wy < b[1]) or (b[1] <= wy < a[1]))
        w, st = 0, None
        for x, d in xs:
            pv = w; w += d
            if pv == 0 and w != 0:
                st = x
            elif pv != 0 and w == 0 and st is not None:
                lo = int(8 + (st - x0) * sc + 0.5); hi = int(8 + (x - x0) * sc + 0.5)
                img[py, max(0, lo):min(size, hi)] = 1
                st = None
    return img


def main():
    d = G.Donor(os.path.join(HEEBO, "Heebo-Medium.ttf"))
    s = 0.60 / d.ink(0x05D4, 1.0)[3]
    G.FLAT_TOL = 0.012
    N, worst = 96, []
    sheet = Image.new("RGB", (N * 14, N * 4), (12, 12, 18))
    for i, ch in enumerate(HEB):
        cp = ord(ch)
        cs = d.outline(cp, s)
        v, t, adv, top = G.mesh_for(d, cp, s, 0.5)
        xs = [p[0] + 0.5 for c in cs for p in c]
        ys = [p[1] for c in cs for p in c]
        pad = G.BAND_W * 1.5
        box = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
        cov = raster(v, t, box, N, "cov")
        binr = raster(v, t, box, N, "bin")
        ref = reference([[(p[0] + 0.5, p[1]) for p in c] for c in cs], box, N)
        err = float(np.abs(binr - ref).sum()) / max(ref.sum(), 1)
        worst.append((err, ch, len(v), len(t) // 3))
        cx, cy = (i % 14) * N, (i // 14) * N * 2
        sheet.paste(Image.fromarray((cov * 255).astype(np.uint8)).convert("RGB"), (cx, cy))
        sheet.paste(Image.fromarray((ref * 255).astype(np.uint8)).convert("RGB"), (cx, cy + N))
    p = os.path.join(HERE, "..", "extract", "aa_band_check.png")
    sheet.save(p)
    worst.sort(reverse=True)
    print(f"{p}   (top = simulated engine AA, bottom = true-outline reference)")
    print("  worst cv>=0 vs true outline (fraction of ink):")
    for e, ch, nv, nt in worst[:6]:
        print(f"    {ch}  {e*100:6.2f}%   V={nv:4d} T={nt:4d}")
    print(f"  median {sorted(w[0] for w in worst)[len(worst)//2]*100:.2f}%")
    print(f"  total  V={sum(w[2] for w in worst):,}  T={sum(w[3] for w in worst):,}")


main()
