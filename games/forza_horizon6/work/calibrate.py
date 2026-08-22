"""Calibrate the mesh coordinate space against the record's own advance/height.

For a straight-edged glyph the AA band is a miter offset of +-W around the true
outline and the solid interior triangles (cv == 1) sit on the outline shrunk by W.
So outline = (cv==1 hull) grown by W, and that must line up with advance/height.
"""
import os
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_font as F                                                # noqa: E402
import fh6_zip as Z                                                 # noqa: E402

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
_, pay = Z.read(os.path.join(GAME, "media", "UI", "Fonts.zip"))

PROBE = (0x48, 0x49, 0x45, 0x4C, 0x54, 0x2E, 0x31, 0x37, 0x410, 0x413, 0x41F)

for fam in ("Horizon_RU_A", "Horizon_A", "Horizon_RU_D"):
    f = F.parse(pay[f"{fam}.vfont"])
    page = pay[f"{fam}.vfont0"]
    by = f.by_cp()
    print(f"=== {fam}")
    print("   cp  ch     adv     hgt |   solid x[min,max]   y[min,max]  |    W   "
          "|   x_em0   x_em1 |   lsb    rsb   inkH")
    for cp in PROBE:
        g = by.get(cp)
        if not g or g.n_verts == 0:
            continue
        v, _ = F.read_mesh(page, g)
        solid = [p for p in v if abs(p[3] - 1.0) < 1e-3]
        if not solid:
            continue
        sx0 = min(p[0] for p in solid); sx1 = max(p[0] for p in solid)
        sy0 = min(p[1] for p in solid); sy1 = max(p[1] for p in solid)
        W = sy0                                   # baseline sits at y == 0
        x0, x1, y1 = sx0 - W, sx1 + W, sy1 + W
        print(f"  {cp:#06x} {chr(cp)!r:4s} {g.adv:7.4f} {g.hgt:7.4f} | "
              f"[{sx0:7.4f},{sx1:7.4f}] [{sy0:7.4f},{sy1:7.4f}] | {W:6.4f} | "
              f"{x0 - F.X_BIAS:7.4f} {x1 - F.X_BIAS:7.4f} | "
              f"{x0 - F.X_BIAS:6.4f} {g.adv - (x1 - F.X_BIAS):6.3f} {y1:6.4f}")
    print()

print("--- band width W and height agreement, whole font ---")
for fam in ("Horizon_RU_A", "Horizon_RU_C", "Horizon_RU_D", "Horizon_A"):
    f = F.parse(pay[f"{fam}.vfont"])
    page = pay[f"{fam}.vfont0"]
    ws, dh, xs = [], [], []
    for g in f.glyphs:
        if g.n_verts == 0:
            continue
        v, _ = F.read_mesh(page, g)
        solid = [p for p in v if abs(p[3] - 1.0) < 1e-3]
        band = [p for p in v if abs(p[3] - 1.0) >= 1e-3]
        if not (solid and band):
            continue
        w = min(p[1] for p in solid) - min(p[1] for p in band)
        ws.append(w)
        if g.hgt > 0.05:
            dh.append((max(p[1] for p in solid) + w) - g.hgt)
        xs.append(min(p[0] for p in solid) - w - F.X_BIAS)
    print(f"  {fam:<14s} n={len(ws):4d}  W median {statistics.median(ws):.5f} "
          f"[{min(ws):.4f},{max(ws):.4f}]   height error median "
          f"{statistics.median(dh):+.5f} max|e| {max(abs(x) for x in dh):.4f}   "
          f"x_em min {min(xs):+.4f}")
