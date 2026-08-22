#!/usr/bin/env python3
"""
find_arabic_art.py — find the Arabic subtitle ARTWORK anywhere, by correlation.

Every previous search assumed something and was wrong when the assumption was:
  * name search      -> assumed the naming convention (`_AR`)   -> missed encrypted names
  * dimension search -> assumed a payload layout (no mipmaps)   -> skipped most textures
  * shape signature  -> assumed 3 stacked bands                 -> a 1-band strip scores 0

This assumes only that the pixels look like the artwork we can already see. The template
is the real Arabic band lifted out of the PRISTINE backup; every texture's every ink band
is normalised to the same small grid and correlated against it, so a match is found at
any resolution, any position, with any number of bands and any name.

    python find_arabic_art.py <forge> [...] [--min 0.6]
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
from find_ar_textures import TEX  # noqa: E402
from find_logo import bands_of  # noqa: E402


def probe(content, maxc=4):
    """[(w, h, header, bcn)] — every plausible payload layout, not just one.

    A block format stores 16 B per 4x4 block (BC7/BC3 -> payload == w*h) or 8 B
    (BC1/BC4 -> w*h/2), each optionally with a full mip chain (x4/3). Accepting only
    one of those silently drops whole classes of texture and reads as "not found",
    which is how the first sweeps missed textures they never even measured.
    """
    out, seen, n = [], set(), len(content)
    for off in range(0, min(n, 512) - 8):
        w, h = struct.unpack_from("<II", content, off)
        if not (32 <= w <= 8192 and 32 <= h <= 8192):
            continue
        # 16 B/block -> BC7 *or* BC3(DXT5); both store w*h bytes and are indistinguishable
        # by size, so BOTH must be decoded. Decoding a BC3 texture as BC7 yields noise,
        # which scores ~0 and looks exactly like "the artwork is not here".
        for bpt, bcn in ((1.0, 7), (1.0, 3), (0.5, 1)):
            for mip in (1.0, 4 / 3):
                hdr = n - int(w * h * bpt * mip)
                key = (w, h, hdr, bcn)
                if 0 < hdr < 512 and key not in seen:
                    seen.add(key)
                    out.append(key)
    return out[:maxc]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = r"F:/Game Lab/Assassin's Creed Mirage"
GRID = (96, 24)          # w, h that every band is normalised to


def norm_band(alpha):
    """Ink band -> a fixed-size, mean-free vector (so it compares across resolutions)."""
    cols = np.where(alpha.max(axis=0) > 8)[0]
    rows = np.where(alpha.max(axis=1) > 8)[0]
    if len(cols) == 0 or len(rows) == 0:
        return None
    crop = alpha[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    im = Image.fromarray(crop).resize(GRID, Image.BILINEAR)
    v = np.asarray(im, dtype=np.float64).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return None if n < 1e-6 else v / n


def template(band=-1):
    """A band of the logo, from the PRISTINE backup (never from a patched forge).

    band=-1 -> the Arabic line: finds copies that still CONTAIN Arabic.
    band=0  -> "ASSASSIN'S CREED": identical in every language variant, so it finds
               EVERY logo texture in the game whatever script or format it uses. That is
               the right probe once the question changed from "where is the Arabic" to
               "which logo asset am I still missing".
    """
    src = os.path.join(GAME, "DataPC_extra.forge.he_backup")
    fg = Forge(src)
    e = [x for x in fg.entries if x.id == 2141045950540][0]
    blob = fg.read(e)
    fg.f.close()
    cfds, _ = acs_cfd.decode_resource(blob, acs_cfd._oodle())
    c = cfds[-1][0]
    img = np.flipud(np.array(Image.frombytes("RGBA", (1072, 600), c[-1072 * 600:], "bcn", (7,))))
    a = img[..., 3]
    b = bands_of(a)
    print(f"template from pristine TitleReveal_AR: bands={b} -> using {b[band]}")
    return norm_band(a[b[band][0]:b[band][1] + 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forges", nargs="+")
    ap.add_argument("--min", type=float, default=0.60)
    ap.add_argument("--dump", type=int, default=10)
    ap.add_argument("--band", type=int, default=-1,
                    help="-1 = the Arabic line; 0 = ASSASSIN'S CREED (every logo)")
    ap.add_argument("--classes-only", action="store_true",
                    help="restrict to the two KNOWN texture classes (faster, but that "
                         "filter is exactly what hid class 491489187)")
    a = ap.parse_args()

    tpl = template(a.band)
    od = acs_cfd._oodle()
    out_dir = os.path.join(HERE, "..", "work", "logo")
    hits = []
    for path in a.forges:
        fg = Forge(path)
        base = os.path.basename(path)
        seen = 0
        for i, e in enumerate(fg.entries):
            try:
                cfds, _ = acs_cfd.decode_resource(fg.read(e), od)
                if not cfds:
                    continue
                c = cfds[-1][0]
            except Exception:
                continue
            if len(c) < 4096:
                continue
            cls, _s, nlen = struct.unpack_from("<Iii", c, 0)
            # NO class filter unless asked. Restricting to the two known texture classes
            # silently skipped class 491489187 — resources whose payloads are exact
            # powers of two (4,194,304 / 2,097,152 / 1,048,576) behind a ~103-119 byte
            # header, i.e. texture data by any measure. Three separate searches came back
            # "0 matches" because of assumptions like this one; `probe()` + a successful
            # decode is evidence enough, so let anything through and let the pixels decide.
            if a.classes_only and cls not in TEX:
                continue
            cands = probe(c)
            if not cands:
                continue
            measured = False
            for w, h, hdr, bcn in cands:
                if w * h > 16_000_000 or w < 32 or h < 16:
                    continue
                nbytes = int(w * h * (0.5 if bcn in (1, 4) else 1.0))
                try:
                    img = np.flipud(np.array(Image.frombytes(
                        "RGBA", (w, h), c[hdr:hdr + nbytes], "bcn", (bcn,))))
                except Exception:
                    continue
                measured = True
                alpha = img[..., 3]
                for bs, be in bands_of(alpha):
                    v = norm_band(alpha[bs:be + 1])
                    if v is None:
                        continue
                    score = float(v @ tpl)
                    if score >= a.min:
                        name = ("<ENCRYPTED>" if nlen & 0x40000000
                                else c[12:12 + (nlen & 0xFFFF)].decode("utf-8", "replace"))
                        hits.append((score, base, e.id, w, h, (bs, be), name, img))
                        print(f"  MATCH {score:.3f}  {base} id={e.id} {w}x{h} bc{bcn} "
                              f"band=({bs},{be})  {name}", flush=True)
            seen += measured
            if (i + 1) % 2000 == 0:
                print(f"   … {base} {i+1:,}/{len(fg.entries):,} measured={seen} "
                      f"hits={len(hits)}", file=sys.stderr, flush=True)
        fg.f.close()
        print(f"## {base}: textures measured={seen:,}")

    hits.sort(key=lambda t: -t[0])
    print(f"\n=== {len(hits)} match(es) at >= {a.min} ===")
    for score, base, rid, w, h, band, name, img in hits[: a.dump]:
        print(f"{score:.3f}  {base}  {rid}  {w}x{h}  band={band}  {name}")
        prev = Image.new("RGB", (w, h), (12, 10, 22))
        im = Image.fromarray(img)
        prev.paste(im, (0, 0), im)
        k = max(1, w // 700)
        prev.resize((w // k, h // k)).save(
            os.path.join(out_dir, f"_ARART_{base}_{rid}.png"))


if __name__ == "__main__":
    main()
