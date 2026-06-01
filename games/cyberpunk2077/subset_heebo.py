"""
Subset Heebo to a minimal glyph set: ASCII printable + Hebrew block.
Result will have ~150 glyphs (vs 591 in our previous Heebo, vs 295 in vanilla raj).
Tests theory that glyph count overflows engine's hardcoded buffer.
"""
import os
from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter

WORK = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\font_v2"
SRC = os.path.join(WORK, "renamed_ttf")
OUT = os.path.join(WORK, "subset_ttf")
os.makedirs(OUT, exist_ok=True)

# Codepoints to keep:
#  ASCII printable: U+0020..U+007E
#  Hebrew block:    U+0590..U+05FF
#  Common punctuation: U+00A0..U+00FF (Latin-1 supplement, common diacritics)
keep = set(range(0x20, 0x7F))
keep |= set(range(0x590, 0x600))
keep |= set(range(0xA0, 0x100))
# CP2077 special tag chars / common puncts
keep |= {0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2013, 0x2014}

unicodes_arg = ",".join(f"U+{cp:04X}" for cp in sorted(keep))
print(f"Subsetting to {len(keep)} codepoints")

for fnt_base in ("rajdhani-regular", "raj-medium", "raj-semibold", "raj-bold", "industry_demi"):
    src = os.path.join(SRC, f"{fnt_base}.ttf")
    if not os.path.exists(src):
        print(f"  SKIP {fnt_base}: not found")
        continue
    out = os.path.join(OUT, f"{fnt_base}.ttf")

    f = TTFont(src)
    subsetter = Subsetter()
    # Glyph filtering by unicode code point
    subsetter.populate(unicodes=list(keep))
    subsetter.subset(f)
    f.save(out)
    glyph_count = f["maxp"].numGlyphs
    print(f"  {fnt_base}.ttf: glyphs={glyph_count} size={os.path.getsize(out):,}")
