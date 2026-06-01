"""
Strip ALL OpenType layout + variable-font tables from Heebo.
Goal: produce a minimal TTF that CP2077's font loader can use without invoking
its text shaper for Hebrew script (which appears to be what's crashing).
"""
import os
from fontTools.ttLib import TTFont

WORK = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\font_v2\static_ttf"
OUT = r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\font_v2\stripped_ttf"
os.makedirs(OUT, exist_ok=True)

# Tables to drop:
# - STAT/avar/fvar/gvar/HVAR/MVAR/VVAR/cvar  → variable-font remnants
# - GSUB/GPOS/GDEF                           → OpenType layout (script-specific shaping)
# - BASE/JSTF/MATH                           → other layout tables
TABLES_TO_DROP = {
    'STAT', 'avar', 'fvar', 'gvar', 'HVAR', 'MVAR', 'VVAR', 'cvar',
    'GSUB', 'GPOS', 'GDEF',
    'BASE', 'JSTF', 'MATH',
}

for name in ('Regular', 'Medium', 'SemiBold', 'Bold'):
    src = os.path.join(WORK, f'Heebo-{name}.ttf')
    if not os.path.exists(src):
        continue
    f = TTFont(src)
    before = sorted(f.keys())
    dropped = []
    for t in TABLES_TO_DROP:
        if t in f:
            del f[t]
            dropped.append(t)
    after = sorted(f.keys())
    out = os.path.join(OUT, f'Heebo-{name}.ttf')
    f.save(out)
    print(f'Heebo-{name}.ttf: dropped {dropped}')
    print(f'  after: {after}')
    print(f'  size:  {os.path.getsize(src):,} -> {os.path.getsize(out):,}')
