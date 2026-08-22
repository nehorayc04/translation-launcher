"""Codepoint table + kern table structure — everything the injector must not break."""
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

for fam in ("Horizon_RU_A", "Horizon_A"):
    f = F.parse(pay[f"{fam}.vfont"])
    cps = [g.cp for g in f.glyphs]
    asc = all(cps[i] < cps[i + 1] for i in range(len(cps) - 2))
    print(f"=== {fam}: {f.n_glyphs} slots, ascending over [0,{len(cps)-2}] = {asc}, "
          f"last two = U+{cps[-2]:04X}, U+{cps[-1]:04X}")
    # where would Hebrew go?
    lo = [c for c in cps[:-1] if c < 0x05D0]
    hi = [c for c in cps[:-1] if c > 0x05EA]
    print(f"    neighbours: ...U+{lo[-1]:04X} | HEBREW U+05D0-05EA | U+{hi[0]:04X}...")
    print(f"    cps > U+0500: {', '.join('U+%04X' % c for c in cps[:-1] if c > 0x500)}")

    print(f"    kern table {len(f.kerns)} B = {len(f.kerns)//12} x 12 B")
    for k in range(3):
        r = f.kerns[k * 12:(k + 1) * 12]
        a32, b32, c32 = struct.unpack("<3I", r)
        a16 = struct.unpack("<6H", r)
        fl = struct.unpack("<3f", r)
        print(f"      [{k}] {r.hex(' ')}  u32=({a32},{b32},{c32})  "
              f"u16={a16}  f32=({fl[0]:.5f},{fl[1]:.5f},{fl[2]:.5f})")
    # do kern fields look like codepoints or like glyph indices?
    ks = [struct.unpack_from("<3I", f.kerns, i * 12) for i in range(len(f.kerns) // 12)]
    a_vals = {a for a, b, c in ks}
    b_vals = {b for a, b, c in ks}
    cpset = set(cps)
    print(f"      field0 range {min(a_vals)}..{max(a_vals)}  in-cpset "
          f"{sum(1 for v in a_vals if v in cpset)}/{len(a_vals)}  "
          f"< nglyphs {sum(1 for v in a_vals if v < f.n_glyphs)}/{len(a_vals)}")
    print(f"      field1 range {min(b_vals)}..{max(b_vals)}  in-cpset "
          f"{sum(1 for v in b_vals if v in cpset)}/{len(b_vals)}  "
          f"< nglyphs {sum(1 for v in b_vals if v < f.n_glyphs)}/{len(b_vals)}")
    print()

# the "true record" model: prefix(24) + 36*N + suffix(12)
print("--- true-record model check ---")
for fam in sorted(n[:-6] for n in pay if n.endswith(".vfont")):
    f = F.parse(pay[f"{fam}.vfont"])
    region = 36 * f.n_glyphs
    n_true, rest = divmod(region - 24 - 12, 36)
    print(f"  {fam:<20s} slots={f.n_glyphs:5d}  region={region:6d}  "
          f"-> 24 + 36*{n_true} + 12, remainder {rest}")
