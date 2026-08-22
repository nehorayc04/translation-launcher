"""Measure the game's Latin metrics and every Heebo weight's Hebrew metrics, so
the injected size/weight is derived from numbers rather than chosen by eye."""
import os
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_font as F                                                # noqa: E402
import fh6_zip as Z                                                 # noqa: E402
from fontTools.ttLib import TTFont                                  # noqa: E402
from fontTools.pens.recordingPen import DecomposingRecordingPen     # noqa: E402
from fontTools.pens.boundsPen import BoundsPen                      # noqa: E402

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
HEEBO = os.path.join(HERE, "..", "..", "spiderman2", "extracted", "_heebo")

# ---------------------------------------------------------------- the game
_, pay = Z.read(os.path.join(GAME, "media", "UI", "Fonts.zip"))
print("=== game fonts (em units) ===")
print(f"{'family':<15s} {'cap':>7} {'x-ht':>7} {'stem':>7} {'stem/cap':>9} "
      f"{'advH':>7} {'lsb':>7}")
game = {}
for fam in ("Horizon_A", "Horizon_B", "Horizon_C", "Horizon_D",
            "Horizon_RU_A", "Horizon_RU_C", "Horizon_RU_D"):
    f = F.parse(pay[f"{fam}.vfont"])
    page = pay[f"{fam}.vfont0"]
    by = f.by_cp()

    def outline_x(cp):
        g = by[cp]
        v, _ = F.read_mesh(page, g)
        solid = [p for p in v if abs(p[3] - 1.0) < 1e-3]
        band = [p for p in v if abs(p[3] - 1.0) >= 1e-3]
        w = min(p[1] for p in solid) - min(p[1] for p in band)
        return sorted({round(p[0], 4) for p in v}), w, g

    xs, w, gh = outline_x(0x48)                     # H
    edges = [(xs[i] + xs[i + 1]) / 2 for i in range(0, len(xs), 2)]
    stem = edges[1] - edges[0]
    cap = gh.hgt
    xht = by[0x78].hgt                              # 'x' — flat top, no overshoot
    game[fam] = dict(cap=cap, xht=xht, stem=stem, adv=gh.adv, w=w)
    print(f"{fam:<15s} {cap:7.4f} {xht:7.4f} {stem:7.4f} {stem/cap:9.3f} "
          f"{gh.adv:7.4f} {(edges[0]-F.X_BIAS):7.4f}")

# ---------------------------------------------------------------- the donor
HEB = "אבגדהוזחטיכךלמםנןסעפףצץקרשת"
FLAT = "הח"          # flat-topped, no overshoot, no ascender/descender
print("\n=== Heebo weights (em units, upem-normalised) ===")
print(f"{'weight':<10s} {'body(ה)':>8} {'stem':>7} {'stem/body':>10} "
      f"{'lamed':>7} {'desc':>7} {'adv(ה)':>7}")
for wname in ("Regular", "Medium", "Bold", "Black"):
    p = os.path.join(HEEBO, f"Heebo-{wname}.ttf")
    if not os.path.exists(p):
        continue
    tt = TTFont(p)
    upem = tt["head"].unitsPerEm
    gs = tt.getGlyphSet()
    cmap = tt.getBestCmap()

    def bbox(ch):
        gn = cmap.get(ord(ch))
        if not gn:
            return None
        bp = BoundsPen(gs)
        gs[gn].draw(bp)
        return None if bp.bounds is None else [b / upem for b in bp.bounds]

    body = max(bbox(c)[3] for c in FLAT)
    lam = bbox("ל")[3]
    desc = min(bbox(c)[1] for c in "קךןףץ")
    adv = tt["hmtx"]["uni05D4" if "uni05D4" in tt.getGlyphOrder()
                     else cmap[0x05D4]][0] / upem
    # stem: the vertical stroke of ה — width of the left leg near mid height
    pen = DecomposingRecordingPen(gs)
    gs[cmap[0x05D4]].draw(pen)
    ys = body * 0.5 * upem
    xs2 = []
    pts = []
    for op, args in pen.value:
        if op in ("moveTo", "lineTo"):
            pts.append(args[0])
        elif op == "qCurveTo":
            pts.extend(args)
        elif op == "curveTo":
            pts.extend(args)
    # crude stem estimate: the narrowest gap between distinct x clusters at top
    top = [q[0] for q in pts if q[1] > body * upem * 0.82]
    top.sort()
    runs, cur = [], [top[0]]
    for v in top[1:]:
        if v - cur[-1] < upem * 0.03:
            cur.append(v)
        else:
            runs.append(cur); cur = [v]
    runs.append(cur)
    stem = (max(runs[0]) - min(runs[0])) / upem if runs else 0
    print(f"{wname:<10s} {body:8.4f} {stem:7.4f} {stem/body:10.3f} "
          f"{lam:7.4f} {desc:7.4f} {adv:7.4f}")

print("\n=== size target ===")
for fam in ("Horizon_A", "Horizon_RU_A"):
    g = game[fam]
    mid = (g["cap"] + g["xht"]) / 2
    print(f"  {fam}: cap {g['cap']:.4f}  x-height {g['xht']:.4f}  "
          f"midpoint {mid:.4f}  0.85*cap {0.85*g['cap']:.4f}  "
          f"stem/cap {g['stem']/g['cap']:.3f}")
