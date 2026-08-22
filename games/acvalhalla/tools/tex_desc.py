#!/usr/bin/env python3
"""
tex_desc.py — READ a texture's dimensions and format from its descriptor.

Every earlier scan inferred dimensions by searching the header for a (w,h) whose product
matched the payload. That is a silent filter: it accepted only the payload layouts it was
told about (first w*h, later also the w*h*4/3 mip chain) and quietly skipped everything
else — a BC1/BC4 texture stores w*h/2 and was therefore invisible. "0 matches" and "this
format does not occur here" look identical from the outside.

The descriptor states it outright. Measured on real resources, relative to the descriptor
start (= 12 + name_len + 1):

    +13  u32 width
    +17  u32 height
    +128 u32 format   (7 = BC7 on the title logos)
    tail u32 payload size in bytes

so dimensions are READ, and the payload ratio only has to be confirmed.

    python tex_desc.py <forge> [--limit N]      # coverage report vs the old heuristic
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "acshadows", "tools"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# bytes-per-texel of the block formats a UI texture realistically uses
#   16 B per 4x4 block -> 1.0   (BC7, BC3/DXT5, BC5)
#    8 B per 4x4 block -> 0.5   (BC1/DXT1, BC4)
RATIOS = (1.0, 0.5)
MIPS = (1.0, 4 / 3)


def parse(content):
    """-> dict(w, h, fmt, payload_off, bpt, mips) or None."""
    if len(content) < 32:
        return None
    nlen = struct.unpack_from("<i", content, 8)[0] & 0xFFFF
    d0 = 12 + nlen + 1
    if d0 + 140 > len(content):
        return None
    w, h = struct.unpack_from("<II", content, d0 + 13)
    if not (4 <= w <= 16384 and 4 <= h <= 16384):
        return None
    fmt = struct.unpack_from("<I", content, d0 + 128)[0]
    for bpt in RATIOS:
        for mip in MIPS:
            size = int(w * h * bpt * mip)
            off = len(content) - size
            if 0 < off - d0 < 4096:                # a plausible descriptor length
                return {"w": w, "h": h, "fmt": fmt, "payload_off": off,
                        "bpt": bpt, "mips": mip != 1.0}
    return None


def main():
    from mirage_forge import Forge
    import acs_cfd
    from find_ar_textures import TEX
    from find_logo import dims_any

    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    fg = Forge(a.forge)
    od = acs_cfd._oodle()
    n_tex = n_new = n_old = 0
    fmts, ratios = {}, {}
    for i, e in enumerate(fg.entries):
        if a.limit and n_tex >= a.limit:
            break
        try:
            cfds, _ = acs_cfd.decode_resource(fg.read(e), od)
            c = cfds[-1][0]
        except Exception:
            continue
        if len(c) < 256:
            continue
        cls = struct.unpack_from("<I", c, 0)[0]
        if cls not in TEX:
            continue
        n_tex += 1
        if dims_any(c):
            n_old += 1
        p = parse(c)
        if p:
            n_new += 1
            fmts[p["fmt"]] = fmts.get(p["fmt"], 0) + 1
            k = (p["bpt"], p["mips"])
            ratios[k] = ratios.get(k, 0) + 1
    fg.f.close()
    print(f"## {os.path.basename(a.forge)}: textures={n_tex:,}")
    print(f"   old heuristic parsed {n_old:,} ({100*n_old/max(1,n_tex):.1f}%)")
    print(f"   descriptor   parsed {n_new:,} ({100*n_new/max(1,n_tex):.1f}%)")
    print(f"   formats: {dict(sorted(fmts.items(), key=lambda x: -x[1]))}")
    print(f"   (bytes/texel, mipped): {dict(sorted(ratios.items(), key=lambda x: -x[1]))}")


if __name__ == "__main__":
    main()
