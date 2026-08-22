"""Verify the FC5 Arabic font end-to-end before touching anything.

  1. does the .fnt's page path hash to the atlas found by CONTENT?
  2. what codepoints does it cover (any Hebrew already)?
  3. how much of the 1024x1024 atlas is free for 27 new glyphs?
  4. what is the SDF encoding (alpha vs distance) so injected glyphs match natively?

  python -u check_font.py
"""
import sys, os, re, struct, io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from fc5_fat import Fat
from fc5_crc64 import name_hash
import numpy as np
from PIL import Image

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(HERE, "..", "extract")
ATLAS_HASH = 0x4121034366bd73a3

fnt = open(os.path.join(OUT, "arabic.fnt"), encoding="utf-8").read()
page = re.search(r'file="([^"]+)"', fnt).group(1)
print(f"page path from .fnt: {page}")
for ext in (".png", ".xbt", ".dds", ".tga"):
    p = re.sub(r"\.\w+$", ext, page)
    h = name_hash(p)
    mark = "   <<< MATCHES the atlas found by content" if h == ATLAS_HASH else ""
    print(f"  {p:<62} -> {h:016x}{mark}")

# ---- coverage
chars = []
for m in re.finditer(r"char id=(\d+)\s+x=([\d.\-]+)\s+y=([\d.\-]+)\s+width=([\d.\-]+)\s+"
                     r"height=([\d.\-]+)\s+xoffset=([\d.\-]+)\s+yoffset=([\d.\-]+)\s+"
                     r"xadvance=([\d.\-]+)", fnt):
    cid = int(m.group(1))
    x, y, w, h, xo, yo, xa = (float(m.group(i)) for i in range(2, 9))
    chars.append((cid, x, y, w, h, xo, yo, xa))
print(f"\nglyphs: {len(chars)}")
cps = sorted(c[0] for c in chars)
print(f"  codepoint range U+{cps[0]:04X} .. U+{cps[-1]:04X}")


def blk(lo, hi, name):
    n = sum(1 for c in cps if lo <= c <= hi)
    if n:
        print(f"  {name:<28} U+{lo:04X}-U+{hi:04X}  {n}")


blk(0x20, 0x7E, "ASCII")
blk(0xA0, 0xFF, "Latin-1")
blk(0x100, 0x17F, "Latin Ext-A")
blk(0x180, 0x24F, "Latin Ext-B")
blk(0x370, 0x3FF, "Greek")
blk(0x400, 0x4FF, "Cyrillic")
blk(0x590, 0x5FF, "HEBREW")
blk(0x600, 0x6FF, "Arabic")
blk(0x750, 0x77F, "Arabic Ext-A")
blk(0xFB50, 0xFDFF, "Arabic Pres-A")
blk(0xFE70, 0xFEFF, "Arabic Pres-B")
heb = [c for c in cps if 0x05D0 <= c <= 0x05EA]
print(f"\n  HEBREW letters present: {len(heb)}/27   -> {'NO INJECTION NEEDED' if len(heb)==27 else 'INJECTION REQUIRED'}")

# ---- free atlas space
f = Fat(os.path.join(PC, "common.fat"))
raw = f.read_data(f.by_hash[ATLAS_HASH])
open(os.path.join(OUT, "arabic_atlas.xbt"), "wb").write(raw)
print(f"\natlas resource {ATLAS_HASH:016x}: {len(raw):,} B  magic={raw[:4]!r}")
dds = raw.find(b"DDS ")
print(f"  DDS header @0x{dds:x}")
hh = struct.unpack_from("<I", raw, dds + 12)[0]
ww = struct.unpack_from("<I", raw, dds + 16)[0]
fourcc = raw[dds + 84:dds + 88]
print(f"  {ww}x{hh}  fourcc={fourcc!r}")
if fourcc == b"DX10":
    fmt = struct.unpack_from("<I", raw, dds + 128)[0]
    print(f"  dxgiFormat={fmt}  (77=BC3_UNORM 78=BC3_SRGB 61=R8 80=BC4)")

im = Image.open(io.BytesIO(raw[dds:])).convert("RGBA")
a = np.array(im)
print(f"  decoded {im.size}  RGB std={a[:,:,:3].std():.4f}  alpha mean={a[:,:,3].mean():.1f}")

alpha = a[:, :, 3]
# a "used" row band = any alpha meaningfully away from the empty value
empty = int(np.bincount(alpha.ravel()).argmax())
used_rows = np.where((np.abs(alpha.astype(int) - empty) > 8).sum(axis=1) > 0)[0]
print(f"  most common alpha (=empty) {empty};  used rows {used_rows.min()}..{used_rows.max()} "
      f"of {alpha.shape[0]}")
# occupancy from the .fnt rects instead (authoritative)
maxy = max(c[2] + c[4] for c in chars)
print(f"  lowest glyph bottom from metrics: y={maxy:.1f}  -> {1024 - maxy:.0f} px of free rows")

# ---- SDF calibration: alpha vs distance on a real glyph
print("\n--- SDF calibration (alpha profile across a glyph edge)")
big = sorted(chars, key=lambda c: -(c[3] * c[4]))[:6]
for cid, x, y, w, h, xo, yo, xa in big[:3]:
    sub = alpha[int(y):int(y + h), int(x):int(x + w)]
    if sub.size == 0:
        continue
    print(f"  U+{cid:04X} rect=({x:.0f},{y:.0f},{w:.0f}x{h:.0f}) alpha min={sub.min()} "
          f"max={sub.max()} mean={sub.mean():.1f} p50={np.percentile(sub,50):.0f}")
hist = np.bincount(alpha.ravel(), minlength=256)
top = np.argsort(hist)[::-1][:8]
print(f"  alpha histogram peaks: {[(int(t), int(hist[t])) for t in top]}")
