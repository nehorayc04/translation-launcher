#!/usr/bin/env python3
"""
find_logo.py — find the title-logo artwork by its ALPHA SIGNATURE, not by name or size.

Name search fails (patch forges encrypt names) and size search fails (we do not know the
logo's resolution in the forge the engine actually reads). What we DO know is what the
artwork looks like: white ink on transparent, laid out as a few full-width horizontal
bands — ASSASSIN'S CREED, MIRAGE, and the script subtitle — inside a wide canvas.

So each texture is decoded and scored on that shape:
  * wide-ish canvas
  * 2-5 horizontal ink bands separated by clear gaps
  * ink spanning most of the width
  * mostly-transparent overall (line art, not a photo)

    python find_logo.py <forge> [--min-w 400] [--dump N]
"""
import argparse
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
from mirage_texdump import find_dims  # noqa: E402,F401

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TEX = {2729961751: "TextureMap", 2560476850: "TextureMapSpec"}


def dims_any(content):
    """(w, h, header) accepting MIPMAPPED textures, not just single-mip.

    `find_dims` requires the payload to be exactly w*h, which silently skips every
    mipmapped texture — and that filter is why the earlier sweeps "found nothing".
    A full mip chain is w*h*(1 + 1/4 + 1/16 + ...) -> w*h*4/3, so both are accepted
    and the top mip is what gets decoded.
    """
    best = None
    n = len(content)
    for off in range(0, min(n, 512) - 8):
        w, h = struct.unpack_from("<II", content, off)
        if not (32 <= w <= 8192 and 32 <= h <= 8192):
            continue
        for mult in (1.0, 4 / 3):
            hdr = n - int(w * h * mult)
            if 0 < hdr < 512:
                best = (w, h, n - int(w * h * mult) if mult == 1.0 else hdr)
    return best


def bands_of(alpha, thr=8, gap=4):
    rows = np.where(alpha.max(axis=1) > thr)[0]
    if len(rows) == 0:
        return []
    out, s, p = [], rows[0], rows[0]
    for r in rows[1:]:
        if r - p > gap:
            out.append((int(s), int(p)))
            s = r
        p = r
    out.append((int(s), int(p)))
    return out


def score(alpha):
    h, w = alpha.shape
    # The lockup is WIDE and stacked. Square canvases are item icons / emblems and
    # flooded the first pass, so the aspect and a real band count are required —
    # the reference (UI_TitleReveal_AR) is 1072x600 = 1.79 with 3 bands.
    if w < h * 1.4:
        return None
    ink = alpha > 8
    cov = ink.mean()
    if not (0.01 < cov < 0.45):          # line art, not a photo or a solid fill
        return None
    b = bands_of(alpha)
    if not (3 <= len(b) <= 6):
        return None
    cols = np.where(ink.max(axis=0))[0]
    if len(cols) == 0:
        return None
    span = (cols.max() - cols.min() + 1) / w
    if span < 0.7:                       # the lockup runs nearly the full width
        return None
    return {"bands": b, "cov": round(float(cov), 3), "span": round(float(span), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forge")
    ap.add_argument("--min-w", type=int, default=400)
    ap.add_argument("--dump", type=int, default=12)
    a = ap.parse_args()

    fg = Forge(a.forge)
    od = acs_cfd._oodle()
    base = os.path.basename(a.forge)
    hits, seen = [], 0
    for i, e in enumerate(fg.entries):
        try:
            cfds, _ = acs_cfd.decode_resource(fg.read(e), od)
            if not cfds:
                continue
            c = cfds[-1][0]
        except Exception:
            continue
        if len(c) < 20_000:
            continue
        cls, _s, nlen = struct.unpack_from("<Iii", c, 0)
        if cls not in TEX:
            continue
        d = dims_any(c)
        if not d:
            continue
        w, h, hdr = d
        if w < a.min_w or w * h > 12_000_000 or h > w * 1.6:
            continue
        seen += 1
        try:
            img = np.flipud(np.array(
                Image.frombytes("RGBA", (w, h), c[hdr:hdr + w * h], "bcn", (7,))))
        except Exception:
            continue
        sc = score(img[..., 3])
        if not sc:
            continue
        nm = ("<enc>" if nlen & 0x40000000
              else c[12:12 + (nlen & 0xFFFF)].decode("utf-8", "replace"))
        hits.append((e.id, w, h, nm, sc, img))
        print(f"  CAND id={e.id:<16} {w}x{h:<5} bands={len(sc['bands'])} "
              f"cov={sc['cov']} span={sc['span']}  {nm[:36]}", flush=True)
        print(f"        {sc['bands']}", flush=True)
        if (i + 1) % 1000 == 0:
            print(f"   … {i+1:,}/{len(fg.entries):,} scanned={seen} hits={len(hits)}",
                  file=sys.stderr, flush=True)
    fg.f.close()
    print(f"## {base}: textures measured={seen:,}  candidates={len(hits)}")

    out = os.path.join(HERE, "..", "work", "logo")
    for rid, w, h, nm, sc, img in hits[: a.dump]:
        im = Image.fromarray(img)
        prev = Image.new("RGB", (w, h), (12, 10, 22))
        prev.paste(im, (0, 0), im)
        k = max(1, w // 700)
        prev.resize((w // k, h // k)).save(
            os.path.join(out, f"_cand_{base}_{rid}.png"))
    if hits:
        print(f"   dumped {min(len(hits), a.dump)} preview(s) to work/logo/_cand_*.png")


if __name__ == "__main__":
    main()
