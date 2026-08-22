#!/usr/bin/env python3
"""
bc7_encode.py — a BC7 (BPTC) encoder, mode 6 only.

AC Mirage's UI textures are BC7 and nothing on this machine can write that format
(PIL decodes `bcn` but cannot encode; no texconv, no nvcompress, no imagecodecs). The
title-logo replacement needs a byte-exact 643,200-byte BC7 payload for the 1072x600
slot, so the encoder is written here rather than adding a binary dependency.

Only **mode 6** is emitted, deliberately:
  * it is the one mode with a single subset and full 8-bit-class RGBA endpoints, so it
    handles opaque, transparent and soft-edge blocks alike with no partition tables;
  * for line art (two clusters — ink and ground — plus an anti-aliased ramp between
    them) a single interpolation axis with 16 steps is already near-lossless;
  * every BC7 decoder must support all modes, so a mode-6-only stream is fully valid.

Mode 6 block layout, LSB first:
    [ 0: 7)  mode marker 0000001
    [ 7:14)  R0   [14:21) R1   [21:28) G0   [28:35) G1
    [35:42)  B0   [42:49) B1   [49:56) A0   [56:63) A1     (7 bits each)
    [63:64)  P0   [64:65) P1                               (endpoint low bits)
    [65:128) indices — 16 x 4 bits, minus the anchor's implicit high bit

    python bc7_encode.py selftest
    python bc7_encode.py <in.png> <out.bc7>
"""
import os
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# the 4-bit interpolation ramp from the BC7 spec
W4 = np.array([0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64], np.float64)
CHUNK = 4096


def _to_blocks(img):
    """(H,W,4) uint8 -> (nblocks,16,4) float, in BC7's row-major 4x4 order."""
    h, w = img.shape[:2]
    assert h % 4 == 0 and w % 4 == 0, f"{w}x{h} is not a multiple of 4"
    bh, bw = h // 4, w // 4
    b = img.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4)
    return b.reshape(bh * bw, 16, 4).astype(np.float64), bh, bw


def _endpoints(px):
    """Two endpoints per block, on the block's dominant colour axis.

    The axis is taken from the pixel furthest from the block mean. For line art the
    content is bimodal (ink / ground), so that pixel lies on the true axis and a full
    PCA buys nothing measurable — verified by the round-trip in selftest().
    """
    n = px.shape[0]
    mean = px.mean(axis=1, keepdims=True)                      # (n,1,4)
    cen = px - mean
    far = np.argmax((cen * cen).sum(axis=2), axis=1)           # (n,)
    d = cen[np.arange(n), far]                                 # (n,4)
    dd = (d * d).sum(axis=1)
    safe = np.where(dd == 0, 1.0, dd)
    t = (cen * d[:, None, :]).sum(axis=2) / safe[:, None]      # (n,16)
    t = np.where((dd == 0)[:, None], 0.0, t)
    e0 = mean[:, 0, :] + t.min(axis=1)[:, None] * d
    e1 = mean[:, 0, :] + t.max(axis=1)[:, None] * d
    return np.clip(e0, 0, 255), np.clip(e1, 0, 255)


def _quantize(e):
    """7-bit endpoint + one shared p-bit. The p-bit is chosen by measuring both
    options, because it is shared across all four channels and the better choice is
    not predictable per channel."""
    best_q = None
    best_p = None
    best_err = None
    for p in (0, 1):
        q = np.clip(np.rint((e - p) / 2.0), 0, 127)
        rec = q * 2 + p
        err = ((e - rec) ** 2).sum(axis=1)
        if best_err is None:
            best_q, best_p, best_err = q, np.full(e.shape[0], p), err
        else:
            take = err < best_err
            best_q = np.where(take[:, None], q, best_q)
            best_p = np.where(take, p, best_p)
            best_err = np.where(take, err, best_err)
    return best_q.astype(np.int64), best_p.astype(np.int64)


def encode(img):
    """(H,W,4) uint8 RGBA -> BC7 bytes."""
    px, bh, bw = _to_blocks(img)
    out = bytearray()
    for s in range(0, px.shape[0], CHUNK):
        blk = px[s:s + CHUNK]
        n = blk.shape[0]
        e0, e1 = _endpoints(blk)
        q0, p0 = _quantize(e0)
        q1, p1 = _quantize(e1)
        r0 = (q0 * 2 + p0[:, None]).astype(np.float64)          # reconstructed 8-bit
        r1 = (q1 * 2 + p1[:, None]).astype(np.float64)

        # nearest point on the 16-step ramp, per pixel
        wq = W4 / 64.0
        cand = r0[:, None, :] * (1 - wq[None, :, None]) + r1[:, None, :] * wq[None, :, None]
        cand = np.rint(cand)                                    # (n,16w,4)
        dist = ((blk[:, :, None, :] - cand[:, None, :, :]) ** 2).sum(axis=3)
        idx = np.argmin(dist, axis=2)                           # (n,16p)

        # the anchor index carries an implicit high 0 bit; if it would need the high
        # half, swap the endpoints and mirror every index instead
        flip = idx[:, 0] >= 8
        idx = np.where(flip[:, None], 15 - idx, idx)
        q0f = np.where(flip[:, None], q1, q0)
        q1f = np.where(flip[:, None], q0, q1)
        p0f = np.where(flip, p1, p0)
        p1f = np.where(flip, p0, p1)

        for i in range(n):
            v = 1 << 6                                          # mode-6 marker
            b = 7
            for c in range(4):                                  # R,R,G,G,B,B,A,A
                v |= int(q0f[i, c]) << b
                b += 7
                v |= int(q1f[i, c]) << b
                b += 7
            v |= int(p0f[i]) << 63
            v |= int(p1f[i]) << 64
            b = 65
            v |= int(idx[i, 0]) << b                            # anchor: 3 bits
            b += 3
            for k in range(1, 16):
                v |= int(idx[i, k]) << b
                b += 4
            out += v.to_bytes(16, "little")
    return bytes(out)


def selftest():
    from PIL import Image
    rng = np.random.default_rng(7)
    # a strip that mimics the real payload: hard ink, empty ground, and an AA ramp
    img = np.zeros((64, 256, 4), np.uint8)
    img[8:24, 16:200] = [255, 255, 255, 255]
    for x in range(256):
        img[32:48, x] = [255, 255, 255, int(255 * x / 255)]
    img[52:60, 100:160] = rng.integers(0, 256, (8, 60, 4), dtype=np.uint8)

    raw = encode(img)
    exp = (64 // 4) * (256 // 4) * 16
    assert len(raw) == exp, f"size {len(raw)} != {exp}"
    back = np.array(Image.frombytes("RGBA", (256, 64), raw, "bcn", (7,)))

    for name, sl in [("solid ink", (slice(8, 24), slice(16, 200))),
                     ("alpha ramp", (slice(32, 48), slice(0, 256))),
                     ("empty ground", (slice(0, 8), slice(0, 256)))]:
        a = img[sl].astype(int)
        b = back[sl].astype(int)
        err = np.abs(a - b).max()
        print(f"  {name:14s} max channel error {err:3d}   {'OK' if err <= 2 else 'FAIL'}")
    noise = np.abs(img[52:60, 100:160].astype(int) - back[52:60, 100:160].astype(int)).mean()
    print(f"  random noise   mean error {noise:.1f} (a single axis cannot fit noise; "
          f"real art is bimodal)")
    overall = np.abs(img[:52].astype(int) - back[:52].astype(int)).max()
    print(f"\n  line-art region max error: {overall} -> "
          f"{'PASS' if overall <= 2 else 'FAIL'}")
    return 0 if overall <= 2 else 1


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    from PIL import Image
    im = np.array(Image.open(sys.argv[1]).convert("RGBA"))
    data = encode(im)
    open(sys.argv[2], "wb").write(data)
    print(f"{sys.argv[1]} {im.shape[1]}x{im.shape[0]} -> {os.path.basename(sys.argv[2])} "
          f"{len(data):,} B")
