"""Extract static TTF instances from variable Heebo font."""
import os, sys, urllib.request
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

WORK = r"C:\Users\nc528\AppData\Local\Temp\font_v2"
os.makedirs(os.path.join(WORK, "static_ttf"), exist_ok=True)

# Re-download variable Heebo (cyber_hebrew.ttf was cleaned up earlier)
src = os.path.join(WORK, "Heebo_variable.ttf")
if not os.path.exists(src):
    url = "https://github.com/google/fonts/raw/main/ofl/heebo/Heebo%5Bwght%5D.ttf"
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, src)
print(f"Variable font: {os.path.getsize(src):,} bytes")

font = TTFont(src)
print(f'  Has fvar (variable): {"fvar" in font}')
print(f'  Glyph count: {font["maxp"].numGlyphs}')

weights = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}
for name, w in weights.items():
    inst = instantiateVariableFont(font, {"wght": w})
    out = os.path.join(WORK, "static_ttf", f"Heebo-{name}.ttf")
    inst.save(out)
    print(f"  Saved Heebo-{name}.ttf ({os.path.getsize(out):,} bytes)")
