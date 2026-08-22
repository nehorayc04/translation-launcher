"""Pull the font from the archive the ENGINE actually wins with.

patch.fat OVERRIDES common.fat, and its copies are DIFFERENT (ffd 40,627 vs 35,410;
atlas 1,398,285 vs 1,048,760) -- building from the common.fat copy would have produced a
perfectly-verified mod that the game never reads.  Always pull the winning copy.

  python -u pull_font.py [archive]      default: patch.fat
"""
import sys, os, struct, io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from fc5_fat import Fat
import numpy as np
from PIL import Image

PC = os.path.join(os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5"),
                  "data_final", "pc")
OUT = os.path.join(HERE, "..", "extract")
FFD_H, XBT_H = 0x236295edc3a3045b, 0x4121034366bd73a3

arch = sys.argv[1] if len(sys.argv) > 1 else "patch.fat"
f = Fat(os.path.join(PC, arch))
ffd = f.read_data(f.by_hash[FFD_H])
xbt = f.read_data(f.by_hash[XBT_H])
open(os.path.join(OUT, "arabic.ffd"), "wb").write(ffd)
open(os.path.join(OUT, "arabic_atlas.xbt"), "wb").write(xbt)
print(f"from {arch}:  ffd {len(ffd):,} B   xbt {len(xbt):,} B")

cnt = struct.unpack_from("<H", ffd, 4)[0]
print(f"  ffd glyph count = {cnt}")

o = struct.unpack_from("<I", xbt, 8)[0]
sz, flags, h, w, pitch, mips = struct.unpack_from("<IIIIII", xbt, o + 4)
fourcc = xbt[o + 84:o + 88]
print(f"  TBX hdr {o} B   DDS {w}x{h} mips={mips} fourcc={fourcc!r}", end="")
ext = 20 if fourcc == b"DX10" else 0
if ext:
    print(f" dxgi={struct.unpack_from('<I', xbt, o + 128)[0]}", end="")
body = len(xbt) - (o + 128 + ext)
print(f"\n  body={body:,}   w*h={w*h:,}   ratio={body/(w*h):.4f}"
      f"   ({'BC3 no mips' if body == w*h else 'BC3 + mip chain' if abs(body/(w*h)-4/3)<.01 else '??'})")

im = Image.open(io.BytesIO(xbt[o:])).convert("RGBA")
a = np.array(im)
print(f"  decoded {im.size}  RGB std={a[:,:,:3].std():.4f}  alpha mean={a[:,:,3].mean():.1f}")
