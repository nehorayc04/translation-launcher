"""Validate the tessellator: triangle area must equal the outline's signed area
(non-zero rule), for every Hebrew letter at every Heebo weight — including the
ones with counters (ם ס ף ע ...), which is where a naive triangulator fails."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_glyphgen as G                                            # noqa: E402

HEEBO = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo")
HEB = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
LATIN = "AHOoBeg8@"


def shoelace(c):
    s = 0.0
    for i in range(len(c)):
        x0, y0 = c[i]
        x1, y1 = c[(i + 1) % len(c)]
        s += x0 * y1 - x1 * y0
    return s / 2


def tri_area(v, t):
    s = 0.0
    for i in range(0, len(t), 3):
        a, b, c = v[t[i]], v[t[i + 1]], v[t[i + 2]]
        s += abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
    return s


worst = 0.0
tot_v = tot_t = 0
for w in ("Regular", "Medium", "Bold", "Black"):
    p = os.path.join(HEEBO, f"Heebo-{w}.ttf")
    if not os.path.exists(p):
        continue
    d = G.Donor(p)
    bad = []
    for ch in HEB + LATIN:
        cp = ord(ch)
        if not d.has(cp):
            bad.append(f"{ch}:missing")
            continue
        cs = d.outline(cp, 1.0)
        v, t = G.tessellate(cs)
        want = abs(sum(shoelace(c) for c in cs))
        got = tri_area(v, t)
        err = abs(got - want) / max(want, 1e-9)
        worst = max(worst, err)
        tot_v += len(v); tot_t += len(t) // 3
        if err > 2e-3:
            bad.append(f"{ch}:{err:.4f}")
    print(f"Heebo-{w:<8s} glyphs {len(HEB)+len(LATIN):3d}  "
          f"{'OK' if not bad else 'FAIL ' + ' '.join(bad)}")

print(f"\nworst relative area error: {worst:.2e}")
print(f"total {tot_v} verts / {tot_t} tris over 4 weights x {len(HEB+LATIN)} glyphs")

d = G.Donor(os.path.join(HEEBO, "Heebo-Medium.ttf"))
print("\nper-glyph cost at Heebo-Medium (scale 0.6/body):")
body = d.ink(ord("ה"), 1.0)[3]
s = 0.60 / body
print(f"  body(ה)={body:.4f}  scale={s:.4f}")
rows = []
for ch in HEB:
    v, t, adv, top = G.mesh_for(d, ord(ch), s, 0.5)
    rows.append((len(v), len(t), ch, adv, top))
rows.sort(reverse=True)
for nv, ni, ch, adv, top in rows[:6]:
    print(f"  {ch}  V={nv:4d} I={ni:5d}  adv={adv:.4f} top={top:.4f}")
print(f"  TOTAL V={sum(r[0] for r in rows)} I={sum(r[1] for r in rows)}  "
      f"page bytes ~= {sum(r[0]*8 + r[1]*2 + 12 for r in rows):,}")
print(f"  stem(ו)={d.stem(ord('ו'), s):.4f}  stem(ה)={d.stem(ord('ה'), s):.4f}")
