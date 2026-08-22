#!/usr/bin/env python3
"""
acs_atlas_inject2.py -- inject Hebrew by changing ONLY pixels + codepoint.

WHY A SECOND INJECTOR
---------------------
Two in-game facts, both from 2026-07-18:

  * `acs_stream_probe.py` flipped the pixels of the largest non-Hebrew glyphs in stream A
    and the menu drew those Arabic letters UPSIDE-DOWN.
    => changing ONLY a record's raster pixels reliably reaches the screen.

  * `acs_atlas_inject.py` (v1) additionally rewrote each repurposed record's metrics
    (advance / bbox / W / H) and the menu kept drawing the slot's ORIGINAL Arabic shape.
    => the metric rewrite is the one thing separating the working case from the broken one.

So v2 makes the minimal edit that is known to work: keep the record 100% vanilla except
its codepoint (+32), and rasterize the Hebrew letter INTO the slot's exact original
W x H canvas. The glyph inherits the Arabic slot's advance/bearings, so spacing and per
letter size will be uneven -- that is a cosmetic follow-up, tuned one variable at a time
once anything Hebrew is on screen at all.

Letterboxing the letter inside the original canvas leaves blank margins, which compress
well and hand the exact-slot fill the headroom it needs (v1 got its headroom by zeroing
dead slot tails; see the black-screen lesson about huge filler).

    python acs_atlas_inject2.py --dry
    python acs_atlas_inject2.py --apply     # GAME MUST BE CLOSED
    python acs_atlas_inject2.py --revert    # restore the pristine resource blobs
"""
import os
import random
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_cfd as C            # noqa: E402
import acs_atlas_inject as AI  # noqa: E402
import acs_stream_probe as SP  # noqa: E402

EDGE = AI.EDGE
FILL = 0.80          # fraction of the slot height the letter body occupies


def render_into(w, h, ch, font_path=AI.HEB_FONT):
    """Rasterize `ch` centred inside a w x h canvas, as an 8-bit SDF-ish coverage map
    matching the game's convention (edge ~128, inside ~168, outside ~40)."""
    SS = 4
    target_h = max(4, int(h * FILL))
    # binary-search a pixel size whose ink height lands on target_h
    lo, hi, best = 4, max(8, h * 3), None
    for _ in range(14):
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid * SS)
        m = f.getmask(ch, mode="L")
        if m.size[0] == 0 or m.size[1] == 0:
            lo = mid + 1
            continue
        img = Image.new("L", m.size, 0)
        img.paste(Image.frombytes("L", m.size, bytes(m)), (0, 0))
        bb = img.getbbox()
        ih = (bb[3] - bb[1]) / SS
        best = (mid, img, bb)
        if ih < target_h:
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        return bytearray(w * h)
    _px, img, bb = best
    crop = img.crop(bb)
    gw = max(1, min(w, round((bb[2] - bb[0]) / SS)))
    gh = max(1, min(h, round((bb[3] - bb[1]) / SS)))
    small = crop.resize((gw, gh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))
    a = np.asarray(small, dtype=np.float32) / 255.0
    sdf = np.clip(EDGE + (a - 0.5) * 96.0, 0, 200).astype(np.uint8)
    # margin 0 = "far outside" (the shipped rasters bottom out at 0 too) AND it is a long
    # constant run, which is what buys the exact-slot fill its headroom.
    canvas = np.zeros((h, w), dtype=np.uint8)
    y0 = max(0, (h - gh) // 2)
    x0 = max(0, (w - gw) // 2)
    canvas[y0:y0 + gh, x0:x0 + gw] = sdf
    return bytearray(canvas.tobytes())


def inject_pixels_only(dec, letters):
    """Repurpose the same slots as v1 but touch ONLY the codepoint and the raster bytes."""
    _g, _c, _s, recs = AI._records(dec)
    probe = [dict(w=1, h=1) for _ in letters]              # slot choice by area only
    cand = sorted([r for r in recs if 0xFB50 <= r["cp"] <= 0xFEFF and r["W"] * r["H"] > 0],
                  key=lambda r: -(r["W"] * r["H"]))[:len(letters)]
    if len(cand) < len(letters):
        raise RuntimeError("not enough presentation-form slots")
    d = bytearray(dec)
    used = 0
    for gi, ch in enumerate(letters):
        r = cand[gi]
        w, h, t = r["W"], r["H"], r["toff"]
        if w <= 0 or h <= 0 or t <= 0 or t + w * h > len(d):
            continue
        struct.pack_into("<I", d, r["o"] + AI.CP_OFF, 0x05D0 + gi)      # ONLY the codepoint
        d[t:t + w * h] = render_into(w, h, ch)                   # ONLY the pixels
        used += 1
    return bytes(d), used


def exact_fill(cfds, new_dec, slot, oodle, seeds=6, window=30, scan_max=8192):
    """Land the encoded blob EXACTLY on the forge slot.

    Grow the object with incompressible filler until the compressed stream hits the slot.

    🔴 TWO BUGS THIS CODE USED TO HAVE (both cost a failed deploy; the loc deployer had
    exactly the same pair -- see acs_loc_deploy.exact_fill):

    1. **Newton assumes one filler byte costs ~one output byte. That premise DOES fail.**
       Measured on the loc side: k=0 -> 623,537 but k=121 -> 623,029, i.e. 508 bytes
       SMALLER after ADDING 121 (the length fields move and every block boundary shifts,
       so the compressor does better). When that happens Newton oscillates instead of
       converging and its window lands nowhere near the answer. So a plain LINEAR SCAN is
       the backstop -- only the weight that actually fails ever pays for it.

    2. **os.urandom() made the search unreproducible.** A filler length that landed on the
       slot in one run was gone the next, so the same weight "fits" or "does not fit"
       depending on the run, and nothing measured in a probe could be reproduced here.
       A seeded PRNG fixes that: same input -> same answer, every run, every machine.

    3. **Re-encoding the WHOLE object per trial made the search unaffordable.** These weights
       decode to 3-13 MB, so one trial cost seconds and a single failed search burned 2.5
       HOURS. But appending filler only changes the LAST 256 KB block -- every earlier
       block is byte-identical. Compressing just that block and MODELLING the container
       size from the known per-block lengths turns a ~3 s trial into ~5 ms, which is what
       makes a wide scan possible at all. **When a search re-does work that cannot have
       changed, fix the search before widening it.**
    """
    di = max(range(len(cfds)), key=lambda i: len(cfds[i][0]))
    other = sum(len(C.build_cfd(cfds[i][0], cfds[i][1], oodle, level=C.LEVEL))
                for i in range(len(cfds)) if i != di)
    cinfo = cfds[di][1]
    pools = [random.Random(0x5ACD0175 + s).randbytes(4 * scan_max + (1 << 16))
             for s in range(seeds)]

    def clen(raw):                            # build_cfd stores raw when it doesn't shrink
        return min(len(oodle.compress(raw, compressor=C.MERMAID, level=C.LEVEL)), len(raw))

    def cfd_size(lens):                       # exactly what build_cfd emits
        return 12 + len(cinfo) + 8 * len(lens) + sum(4 + L for L in lens)

    nfull = len(new_dec) // C.BLOCK
    head_lens = [clen(new_dec[i * C.BLOCK:(i + 1) * C.BLOCK]) for i in range(nfull)]
    tail = new_dec[nfull * C.BLOCK:]

    def enc(pool, k):                         # only the tail block is ever recompressed
        t = tail + pool[:k]
        lens = list(head_lens)
        for off in range(0, max(1, len(t)), C.BLOCK):
            lens.append(clen(t[off:off + C.BLOCK]))
        return other + cfd_size(lens)

    def finish(pool, k):
        parts = list(cfds)
        parts[di] = (new_dec + pool[:k], cinfo)
        return b"".join(C.build_cfd(dd, ci, oodle, level=C.LEVEL) for dd, ci in parts)

    if enc(pools[0], 0) > slot:
        return None                           # genuinely too big -- reseeding cannot help

    # 🔴 Scan AROUND k0, not from zero. An earlier backstop scanned 0..1200 while the answer
    # for a 12.8 MB weight sat at ~15,308 -- it was searching a region the answer could not
    # be in. And scan OUTWARD from k0 so the first hit is the SMALLEST filler that works:
    # less appended filler is strictly safer (a payload that outgrows the object's declared
    # size is what black-screened the game once already).
    k0 = max(0, slot - enc(pools[0], 0))
    for pool in pools:
        for d in range(scan_max):
            for kk in ((k0 + d, k0 - d) if d else (k0,)):
                if kk >= 0 and enc(pool, kk) == slot:
                    return finish(pool, kk)
    return None


def run(mode):
    oodle = C._oodle()
    letters = AI.HEB
    built = []
    AI._POOL = os.urandom(4 << 20)
    for _cfg, idx in AI.WEIGHTS:
        forge, off, size, blob, cfds, dec = SP.pristine(idx, oodle)
        nd, used = inject_pixels_only(dec, letters)
        assert len(nd) == len(dec)
        # The object fits the slot with 5-8 KB to spare, but the compressed size is not
        # continuous in the filler length -- one extra byte can move it by three, so the
        # exact byte can fall in a gap. Re-seeding the filler CONTENT reshuffles where
        # those jumps land (the same trick acs_loc_deploy.exact_fill uses), so just retry
        # with fresh pools instead of giving up on the weight.
        nb = exact_fill(cfds, nd, size, oodle)
        ok = nb is not None and len(nb) == size and AI._decoder_ok(nb)
        heb = 0
        if ok:
            c2, _ = C.decode_resource(nb, oodle)
            d2 = max((x for x, _ in c2), key=len)
            cps = {r["cp"] for r in AI._records(d2)[3]}
            heb = sum(1 for i in range(27) if (0x05D0 + i) in cps)
        print(f"  idx={idx:<6} ({os.path.basename(forge):<28}) slot={size:>10,} "
              f"written={used:<3} Heb={heb:>2}/27 -> {'OK' if ok and heb == 27 else 'FAIL'}")
        built.append((forge, off, size, nb if (ok and heb == 27) else None))

    ready = [b for b in built if b[3] is not None]
    if mode != "--apply":
        print(f"\n--dry: {len(ready)}/{len(built)} weights built. Pass --apply to deploy.")
        return 0 if len(ready) == len(built) else 1
    if len(ready) != len(built):
        print("\nnot all weights built -- aborting.")
        return 1
    for forge, off, size, nb in ready:
        AI.verify_slot(forge, off, size)     # the forge may have changed since the backup
        with open(forge, "r+b") as f:
            f.seek(off)
            f.write(nb)
        print(f"WROTE @0x{off:x} in {os.path.basename(forge)} ({size:,} B)")
    print("\nDEPLOYED (pixels + codepoint only; every metric left vanilla).\n"
          "Cold-launch -> main menu. HEBREW LETTERS (uneven spacing/size is expected)\n"
          "=> the font gate is CLOSED and only metrics remain to tune.\n"
          "Undo with:  python acs_atlas_inject2.py --revert")
    return 0


def revert():
    """Restore the untouched blobs saved by acs_atlas_inject."""
    import glob
    n = 0
    for p in sorted(glob.glob(os.path.join(HERE, "_atlasbak_*.bin"))):
        with open(p, "rb") as g:
            off, size = struct.unpack("<QQ", g.read(16))
            rest = g.read()
        if len(rest) == size:
            forge, blob = AI._P2, rest
        else:
            z = rest.index(b"\x00")
            forge, blob = rest[:z].decode(), rest[z + 1:]
        with open(forge, "r+b") as f:
            f.seek(off)
            f.write(blob)
        print(f"  restored {os.path.basename(p)} -> {os.path.basename(forge)}")
        n += 1
    print(f"reverted {n} weights to pristine.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    sys.exit(revert() if a == "--revert" else run(a))
