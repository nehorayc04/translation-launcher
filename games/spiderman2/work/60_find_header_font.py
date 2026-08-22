"""Which font renders the lobby HEADER? Body text already shows Hebrew (we
swapped every AzbukaPro face), but the header is still tofu -> it uses a font
we did NOT swap. Scan d/userinterface CSS for every `font-family:` paired with
its `font-size:` so we can see which family the big header text uses (the only
un-swapped fontmap face is MagicSpell)."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
buf = open(os.path.join(GAME, "d", "userinterface"), "rb").read()

# Find every font-family occurrence and the nearest preceding font-size
fam_re = re.compile(rb'family:\s*"([^"]{1,40})"')
counts = {}
big = []
for m in fam_re.finditer(buf):
    fam = m.group(1).decode("latin-1")
    counts[fam] = counts.get(fam, 0) + 1
    # look back ~120 bytes for a font-size
    back = buf[max(0, m.start()-160):m.start()]
    sm = re.findall(rb'font-size:\s*([0-9.]+)(vh|px|vw|em)?', back)
    if sm:
        try:
            val = float(sm[-1][0]); unit = sm[-1][1].decode() if sm[-1][1] else ""
        except Exception:
            val, unit = 0, ""
        if unit == "vh" and val >= 5:    # large headers
            big.append((val, unit, fam, m.start()))

print("=== font-family usage counts in d/userinterface ===")
for fam, c in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {c:>5}x  {fam!r}")

print("\n=== LARGE text (font-size >= 5vh) -> family ===")
for val, unit, fam, off in sorted(big, reverse=True)[:40]:
    print(f"  [{off:>9}] {val:>7}{unit}  family={fam!r}")
