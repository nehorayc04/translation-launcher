#!/usr/bin/env python3
"""
mirage_texdump.py — decode any AC Mirage texture resource to a PNG so it can be LOOKED at.

Dimensions are not assumed: the descriptor is scanned for a `u32 w, u32 h` pair whose
product exactly equals `len(content) - header`, which pins both the size and the header
length in one step (BC7 is 1 byte per texel, so w*h IS the payload length for a
single-mip slot). The payload is then flipped, because Anvil stores textures BOTTOM-UP.

    python mirage_texdump.py <forge> <resource_id> [out.png]
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

from mirage_forge import Forge  # noqa: E402
import acs_cfd  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_dims(content):
    """(w, h, header_len) — the pair whose product is exactly the trailing payload."""
    best = None
    for off in range(0, min(len(content), 512) - 8):
        w, h = struct.unpack_from("<II", content, off)
        if not (32 <= w <= 8192 and 32 <= h <= 8192):
            continue
        hdr = len(content) - w * h
        if 0 < hdr < 512:
            # prefer the LAST such match: the descriptor repeats the dims, and the
            # copy nearest the payload is the one that describes it
            best = (w, h, hdr)
    return best


def dump(forge, res_id, out=None):
    fg = Forge(forge)
    od = acs_cfd._oodle()
    m = [e for e in fg.entries if e.id == int(res_id)]
    if not m:
        raise SystemExit(f"id {res_id} not in {os.path.basename(forge)}")
    cfds, _ = acs_cfd.decode_resource(fg.read(m[0]), od)
    fg.f.close()
    c = cfds[-1][0]
    cls, size, nlen = struct.unpack_from("<Iii", c, 0)
    name = c[12:12 + nlen].decode("utf-8", "replace") if 0 < nlen < 300 else "?"
    dims = find_dims(c)
    print(f"# {name}  cls={cls} content={len(c):,}")
    if not dims:
        print("  no single-mip w*h fits the payload (mipped or a different format)")
        return None
    w, h, hdr = dims
    print(f"  {w}x{h}  header={hdr}  payload={w*h:,}")
    img = np.flipud(np.array(Image.frombytes("RGBA", (w, h), c[hdr:hdr + w * h], "bcn", (7,))))
    a = img[..., 3]
    rows = np.where(a.max(axis=1) > 8)[0]
    bands = []
    if len(rows):
        s = p = rows[0]
        for r in rows[1:]:
            if r - p > 4:
                bands.append((int(s), int(p)))
                s = r
            p = r
        bands.append((int(s), int(p)))
    print(f"  ink bands: {bands}")
    out = out or os.path.join(HERE, "..", "work", "logo", f"_tex_{name}.png")
    im = Image.fromarray(img)
    prev = Image.new("RGB", (w, h), (12, 10, 22))
    prev.paste(im, (0, 0), im)
    prev.save(out)
    print(f"  -> {os.path.basename(out)}")
    return out


if __name__ == "__main__":
    dump(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
