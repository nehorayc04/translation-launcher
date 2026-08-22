#!/usr/bin/env python3
"""probe_ar.py — measure the 6 Arabic textures before editing: dims, mips, bands, trailer."""
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402
from find_logo import bands_of  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FORGE = r"F:/Game Lab/Assassin's Creed Mirage/DataPC_extra.forge"
IDS = [2181436741074, 2181436741075, 2181436742028,
       2141045950540, 2141045950541, 2141045950553]


def dims_scan(content):
    """Every (w,h,header) whose w*h or full-mip-chain matches the trailing payload."""
    out, n = [], len(content)
    for off in range(0, min(n, 512) - 8):
        w, h = struct.unpack_from("<II", content, off)
        if not (32 <= w <= 8192 and 32 <= h <= 8192):
            continue
        for label, sz in (("single", w * h), ("mipchain", int(w * h * 4 / 3))):
            hdr = n - sz
            if 0 < hdr < 512:
                out.append((w, h, hdr, label, off))
    return out


def main():
    fg = Forge(FORGE)
    od = acs_cfd._oodle()
    ents = {e.id: e for e in fg.entries}
    for rid in IDS:
        e = ents[rid]
        blob = fg.read(e)
        cfds, consumed = acs_cfd.decode_resource(blob, od)
        trailer = blob[consumed:]
        c = cfds[-1][0]
        cls, size_field, nlen = struct.unpack_from("<Iii", c, 0)
        name = c[12:12 + nlen].decode("utf-8", "replace")
        cand = dims_scan(c)
        print(f"\n=== {name}")
        print(f"  id={rid} on-disk slot={e.size:,}  content={len(c):,}  cfds={len(cfds)}  "
              f"trailer={len(trailer)}B (all-zero={trailer == b'0' * 0 or set(trailer) <= {0}})")
        print(f"  dim candidates: {cand}")
        if not cand:
            continue
        w, h, hdr, label, _ = cand[0]
        px = c[hdr:]
        print(f"  -> {w}x{h} header={hdr} payload={len(px):,} "
              f"({'SINGLE MIP' if len(px) == w * h else 'HAS MIPS: %.3fx' % (len(px)/(w*h))})")
        img = np.flipud(np.array(Image.frombytes("RGBA", (w, h), px[:w * h], "bcn", (7,))))
        b = bands_of(img[..., 3])
        print(f"  bands={b}  H%4={h % 4} W%4={w % 4}")
    fg.f.close()


if __name__ == "__main__":
    main()
