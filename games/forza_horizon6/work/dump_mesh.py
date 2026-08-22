"""Print one glyph's mesh in full so the vertex semantics can be read off."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_font as F                                                # noqa: E402
import fh6_zip as Z                                                 # noqa: E402

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
_, pay = Z.read(os.path.join(GAME, "media", "UI", "Fonts.zip"))
fam = sys.argv[1] if len(sys.argv) > 1 else "Horizon_RU_A"
cp = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x48
f = F.parse(pay[f"{fam}.vfont"])
page = pay[f"{fam}.vfont0"]
gm = f.glyph_map()
g = gm[cp]
v, idx = F.read_mesh(page, g)

print(f"{fam} U+{cp:04X} {chr(cp)!r}: V={g.n_verts} I={g.n_indices} off={g.data_off}")
print(f"record: {g.raw.hex(' ')}")
print("\n  i        x        y       cu       cv")
for i, (x, y, cu, cv) in enumerate(v):
    print(f"  {i:3d} {x:8.4f} {y:8.4f} {cu:8.3f} {cv:8.3f}")
print("\nindices (triangles):")
for t in range(0, len(idx), 3):
    print(f"  {idx[t]:4d} {idx[t+1]:4d} {idx[t+2]:4d}", end="")
    if t % 15 == 12:
        print()
print()

# how many distinct positions?
pos = {(round(p[0], 5), round(p[1], 5)) for p in v}
print(f"\ndistinct (x,y): {len(pos)} of {len(v)}")
xs = sorted({round(p[0], 4) for p in v})
ys = sorted({round(p[1], 4) for p in v})
print(f"distinct x ({len(xs)}): {xs}")
print(f"distinct y ({len(ys)}): {ys}")

# vertices used by triangles that are degenerate in position?
deg = 0
for t in range(0, len(idx), 3):
    a, b, c = (v[idx[t]], v[idx[t + 1]], v[idx[t + 2]])
    ar = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))
    if ar < 1e-9:
        deg += 1
print(f"degenerate triangles: {deg} of {len(idx)//3}")
