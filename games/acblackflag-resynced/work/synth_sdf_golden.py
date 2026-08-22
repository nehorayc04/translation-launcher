#!/usr/bin/env python3
"""GOLDEN TEST: re-bake a glyph from the loose AvenirNextWorld TTF with the deduced SDF
parameters and compare byte-for-byte against the shipped atlas raster.

Deduced model:   value = clamp(0,255, round(128 + 16*d))   d = signed distance in px, +inside
                 bitmap box = ink bbox expanded by PAD px on every side
If this reproduces the vendor bytes, Hebrew glyphs can be authored with certainty.
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "atlas")
FDIR = os.path.join(HERE, "refmods", "he_fonts")
REC, FH = 36, 32
SS = 8          # supersample
PX = 40.0       # atlas pixel size


def parse(buf):
    g = buf.find(b"GFOF")
    faces, p = [], g + 36
    while True:
        cnt = struct.unpack_from("<I", buf, p)[0]
        if cnt > 20000 or buf[p + 4:p + 20] != b"\0" * 16:
            break
        upem, z, one = struct.unpack_from("<IIf", buf, p + 20)
        if upem not in (1000, 1024) or z or one != 1.0:
            break
        faces.append([struct.unpack_from("<I7fI", buf, p + FH + i * REC) for i in range(cnt)])
        p += FH + cnt * REC
    return g, faces


def shipped(fn, cp):
    buf = open(os.path.join(D, fn), "rb").read()
    g, faces = parse(buf)
    for fi, fa in enumerate(faces):
        for r in fa:
            if r[0] == cp:
                W, H = int(r[6]), int(r[7])
                return np.frombuffer(buf[g + r[8]:g + r[8] + W * H], np.uint8).reshape(H, W).copy(), r, fi
    return None, None, None


def bake(ttf, ch, W, H, pad, edge=128.0, slope=16.0):
    """Render ch, build the SDF into a WxH box whose ink is inset by `pad` px."""
    f = ImageFont.truetype(ttf, int(round(PX * SS)))
    big = Image.new("L", (W * SS * 2, H * SS * 2), 0)
    ImageDraw.Draw(big).text((W * SS // 2, H * SS + 200), ch, fill=255, font=f, anchor="ls")
    a = np.array(big)
    ys, xs = np.nonzero(a > 127)
    if len(xs) == 0:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    mask = a[y0:y1 + 1, x0:x1 + 1] > 127
    ih, iw = mask.shape
    # boundary points of the mask, in subpixel coords relative to ink top-left
    m = mask
    edge_mask = m & ~(np.pad(m, 1)[:-2, 1:-1] & np.pad(m, 1)[2:, 1:-1] &
                      np.pad(m, 1)[1:-1, :-2] & np.pad(m, 1)[1:-1, 2:])
    by, bx = np.nonzero(edge_mask)
    bpts = np.stack([bx + 0.5, by + 0.5], 1).astype(np.float32)      # subpixel centres
    # output pixel centres, in the same subpixel coord system:
    # box left edge sits pad px left of the ink left edge -> ink x=0 is at box x=pad
    gx = (np.arange(W) + 0.5 - pad) * SS
    gy = (np.arange(H) + 0.5 - pad) * SS
    GX, GY = np.meshgrid(gx, gy)
    pts = np.stack([GX.ravel(), GY.ravel()], 1).astype(np.float32)
    d = np.empty(len(pts), np.float32)
    CH = 4096
    for i in range(0, len(pts), CH):
        chunk = pts[i:i + CH]
        dist = np.sqrt(((chunk[:, None, :] - bpts[None, :, :]) ** 2).sum(-1)).min(1)
        d[i:i + CH] = dist
    d = d.reshape(H, W) / SS                       # px
    # sign: inside = +
    ix = np.clip(np.round(GX - 0.5).astype(int), 0, iw - 1)
    iy = np.clip(np.round(GY - 0.5).astype(int), 0, ih - 1)
    inside = mask[iy, ix] & (GX >= 0) & (GX < iw) & (GY >= 0) & (GY < ih)
    sd = np.where(inside, d, -d)
    v = np.clip(np.round(edge + slope * sd), 0, 255).astype(np.uint8)
    return v, (iw / SS, ih / SS)


TESTS = [("16248_88c2952c.bin", "AvenirNextWorld-Regular.ttf", "A", 0x41),
         ("16243_88c2952a.bin", "AvenirNextWorld-Demi.ttf", "A", 0x41),
         ("16245_88c2952b.bin", "AvenirNextWorld-Light.ttf", "M", 0x4D),
         ("70970_88c902b3.bin", "AvenirNextWorld-Light.ttf", "E", 0x45)]

for fn, ttf, ch, cp in TESTS:
    ref, rec, fi = shipped(fn, cp)
    if ref is None:
        print(fn, "cp missing"); continue
    H, W = ref.shape
    print("=" * 96)
    print("%s  U+%04X  face%d  W=%d H=%d  bbox=(%.2f,%.2f,%.2f,%.2f) adv=%.2f"
          % (fn, cp, fi, W, H, rec[2], rec[3], rec[4], rec[5], rec[1]))
    best = None
    for pad in (8.0, 8.5, 9.0, 9.5, 10.0):
        out = bake(os.path.join(FDIR, ttf), ch, W, H, pad)
        if out is None:
            continue
        v, ink = out
        err = np.abs(v.astype(int) - ref.astype(int))
        line = ("   pad=%4.1f ink=%.1fx%.1f  meanAbsErr=%6.2f  p95=%3d  max=%3d  exact=%.1f%%  <=4:%.1f%%"
                % (pad, ink[0], ink[1], err.mean(), np.percentile(err, 95), err.max(),
                   100 * (err == 0).mean(), 100 * (err <= 4).mean()))
        print(line)
        if best is None or err.mean() < best[0]:
            best = (err.mean(), pad, v)
    v = best[2]
    print("   best pad=%.1f" % best[1])
    ramp = " .:-=+*#%@"
    for y in range(0, H, max(1, H // 20)):
        a = "".join(ramp[min(9, int(ref[y, x]) * 10 // 256)] for x in range(W))
        b = "".join(ramp[min(9, int(v[y, x]) * 10 // 256)] for x in range(W))
        print("   |%s|   |%s|" % (a, b))
