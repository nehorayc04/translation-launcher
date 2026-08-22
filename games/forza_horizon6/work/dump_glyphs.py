"""Dump every field of the 36-byte glyph record + the 204-byte header, so the
injector can be built against measured values instead of guesses."""
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import fh6_font as F                                                # noqa: E402
import fh6_zip as Z                                                 # noqa: E402

GAME = os.environ.get("FH6_GAME", r"C:\Games\Forza Horizon 6")
_, pay = Z.read(os.path.join(GAME, "media", "UI", "Fonts.zip"))
fam = sys.argv[1] if len(sys.argv) > 1 else "Horizon_RU_A"
f = F.parse(pay[f"{fam}.vfont"])
page = pay[f"{fam}.vfont0"]

print(f"=== {fam}: {f.n_glyphs} glyphs, {f.n_kerns} kerns, {f.n_pages} pages")
print("\n--- header 0x88..0xCC as f32 ---")
for o in range(0x88, F.HDR, 4):
    v, = struct.unpack_from("<f", f.header, o)
    i, = struct.unpack_from("<I", f.header, o)
    print(f"  +0x{o:03x}  f32={v:14.5f}   u32={i:<12} i32={struct.unpack_from('<i', f.header, o)[0]}")

print("\n--- page table (8 B each) ---")
for i in range(f.n_pages):
    print(f"  page {i}: {f.pages[i*8:(i+1)*8].hex(' ')}")

print("\n--- glyph records: field map ---")
print("  idx  cp(rec)  ->cp(geom)  f0(+00)   nV   nI   off(+08)   +0c        +10       +14      "
      "cp(+18)  f1c        f20")
gm = f.glyph_map()
inv = {id(g): cp for cp, g in gm.items()}
want = [0x20, 0x21, 0x30, 0x31, 0x38, 0x41, 0x48, 0x4F, 0x61, 0x6F,
        0x410, 0x411, 0x416, 0x424, 0x44F]
for i, g in enumerate(f.glyphs):
    geom_cp = inv.get(id(g))
    if not (g.cp in want or (geom_cp or 0) in want or i < 3 or i >= f.n_glyphs - 3):
        continue
    r = g.raw
    f0, = struct.unpack_from("<f", r, 0x00)
    a, b = struct.unpack_from("<2H", r, 0x04)
    off, = struct.unpack_from("<I", r, 0x08)
    x0c, = struct.unpack_from("<I", r, 0x0c)
    f10, = struct.unpack_from("<f", r, 0x10)
    f14, = struct.unpack_from("<f", r, 0x14)
    cp, = struct.unpack_from("<I", r, 0x18)
    f1c, = struct.unpack_from("<f", r, 0x1c)
    f20, = struct.unpack_from("<f", r, 0x20)
    gc = f"U+{geom_cp:04X}" if geom_cp else "  --  "
    print(f"  {i:4d}  U+{cp:04X}   {gc}   {f0:8.4f} {a:4d} {b:4d} {off:9d}  "
          f"{x0c:#010x} {f10:9.4f} {f14:8.4f}  U+{cp:04X}  {f1c:9.4f} {f20:8.4f}")

print("\n--- raw hex of a few records ---")
for i in (0, 1, 2, 35, 36):
    if i < f.n_glyphs:
        print(f"  [{i:3d}] {f.glyphs[i].raw.hex(' ')}")

print("\n--- mesh bounds for a few glyphs ---")
for cp in (0x41, 0x48, 0x4F, 0x6F, 0x410, 0x416, 0x31):
    g = gm.get(cp)
    if not g or g.n_verts == 0:
        continue
    v, idx = F.read_mesh(page, g)
    xs = [p[0] for p in v]
    ys = [p[1] for p in v]
    cu = [p[2] for p in v]
    cv = [p[3] for p in v]
    print(f"  U+{cp:04X} {chr(cp)!r:6s} V={g.n_verts:4d} I={g.n_indices:4d}  "
          f"x[{min(xs):7.4f},{max(xs):7.4f}] y[{min(ys):7.4f},{max(ys):7.4f}]  "
          f"cu[{min(cu):6.3f},{max(cu):6.3f}] cv[{min(cv):6.3f},{max(cv):6.3f}]  "
          f"imax={max(idx)}")

print("\n--- last glyph's mesh end vs page end ---")
gs = sorted(f.glyphs, key=lambda g: g.data_off)
last = gs[-1]
end = last.data_off + 12 + 8 * last.n_verts + 2 * last.n_indices
print(f"  last data_off={last.data_off} end={end} page_len={len(page)} tail={len(page)-end}")
print(f"  tail bytes: {page[end:end+32].hex(' ')}")
print(f"  page head : {page[:16].hex(' ')}")
