#!/usr/bin/env python3
"""
splice_bc7.py — build the replacement BC7 payload by re-encoding ONLY the block rows
the Hebrew line touches, and copying Ubisoft's own blocks for everything above.

Why splice instead of re-encoding the whole texture
---------------------------------------------------
The shipped artwork carries a soft shadow baked as near-black RGB under low alpha
(298,715 texels at alpha 1..199, RGB mean 18). Those blocks are NOT collinear in RGBA
space, so a single-axis BC7 mode cannot fit them — a full re-encode either smears them
(max channel error 151, measured) or, if the RGB is flattened to white to make the fit
possible, turns the shadow into a visible halo around ASSASSIN'S CREED.

Neither is necessary: BC7 is a fixed 16-byte-per-4x4-block format with no inter-block
state, so the original bytes for the untouched bands can be carried over verbatim and
only the Hebrew band re-encoded. That is the same "touch only what changed" discipline
the forge deploys use, applied one level down.

🔴 The payload is stored BOTTOM-UP. Verified, not assumed: decoding the raw blocks and
comparing against the reference PNG gives 472,994 alpha differences as-is and exactly 0
after a vertical flip. So the displayed band 3 (y 384..599) lives in RAW block rows
0..53, and the bands to preserve are the raw rows ABOVE that. Splicing on the naive
top-down row would have kept the Arabic and overwritten ASSASSIN'S CREED — and the
per-band error check would still have looked clean, because both halves are "correct",
just swapped.

Split: displayed y=384 -> raw y 0..215 -> raw block rows 0..53. Verified clear in the
shipped texture — band 2 ends at y=372 and band 3's ink starts at y=393, so nothing
sits in the 12 px either side of the cut.

    python splice_bc7.py
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

from bc7_encode import encode  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

W, H = 1072, 600
BLOCKS_X, BLOCKS_Y = W // 4, H // 4          # 268 x 150
SPLIT_Y = 384                                 # keep everything above this verbatim
SPLIT_ROW = SPLIT_Y // 4                      # block row 96
ORIG_BIN = os.path.join(HERE, "AR_Map_PC.bin")
HDR = 264                                     # asset header before the pixel data
NEW_PNG = os.path.join(HERE, "MIRAGE_HE_final.png")
LOGO_REF = os.path.join(HERE, "MIRAGE_TitleReveal_AR_original.png")
OUT = os.path.join(HERE, "MIRAGE_HE_final.bc7")


def decode(payload):
    """Raw payload -> the image as DISPLAYED (the store is bottom-up)."""
    return np.flipud(np.array(Image.frombytes("RGBA", (W, H), payload, "bcn", (7,))))


def main():
    blob = open(ORIG_BIN, "rb").read()
    orig = blob[HDR:]
    need = BLOCKS_X * BLOCKS_Y * 16
    assert len(orig) == need, f"pixel payload {len(orig)} != {need}"

    img = np.array(Image.open(NEW_PNG).convert("RGBA"))
    assert img.shape[:2] == (H, W), f"{img.shape} != {(H, W, 4)}"

    # prove the orientation instead of trusting it — the whole splice depends on it
    dec_asis = np.array(Image.frombytes("RGBA", (W, H), orig, "bcn", (7,)))[..., 3].astype(int)
    ref_alpha = np.array(Image.open(LOGO_REF).convert("RGBA"))[..., 3].astype(int)
    d_asis = int((dec_asis != ref_alpha).sum())
    d_flip = int((np.flipud(dec_asis) != ref_alpha).sum())
    print(f"# orientation probe: as-is {d_asis:,} diffs · flipped {d_flip:,} diffs "
          f"-> store is {'BOTTOM-UP' if d_flip < d_asis else 'TOP-DOWN'}")
    assert d_flip == 0, "the payload is not a clean vertical flip of the reference"

    # sanity: what we keep must be identical in the new image
    diff_keep = int((decode(orig)[:SPLIT_Y, :, 3].astype(int)
                     != img[:SPLIT_Y, :, 3].astype(int)).sum())
    print(f"# alpha differences in the kept bands: {diff_keep} "
          f"({'OK — bands 1+2 are verbatim' if diff_keep == 0 else 'UNEXPECTED'})")
    assert diff_keep == 0

    # displayed y >= SPLIT_Y  <->  raw y 0..(H-SPLIT_Y-1)  <->  raw block rows 0..n-1
    n_rows = (H - SPLIT_Y) // 4                                  # 54
    flipped = np.flipud(img)                                     # into store order
    enc = encode(np.ascontiguousarray(flipped[: n_rows * 4]))
    assert len(enc) == n_rows * BLOCKS_X * 16

    keep = orig[n_rows * BLOCKS_X * 16:]
    out = enc + keep
    assert len(out) == need, f"{len(out)} != {need}"
    open(OUT, "wb").write(out)

    back = decode(out).astype(int)
    ref = decode(orig).astype(int)
    top = np.abs(back[:SPLIT_Y] - ref[:SPLIT_Y]).max()
    bot = np.abs(back[SPLIT_Y:] - img[SPLIT_Y:].astype(int)).max()
    print(f"# kept verbatim  : {len(keep):,} / {need:,} ({100*len(keep)/need:.1f}%)  "
          f"raw block rows {n_rows}..{BLOCKS_Y-1}")
    print(f"# re-encoded     : {len(enc):,}  raw block rows 0..{n_rows-1}")
    print(f"# ASSASSIN'S CREED / MIRAGE vs shipped : max channel error {top}  "
          f"{'IDENTICAL' if top == 0 else 'CHANGED'}")
    print(f"# Hebrew line vs the new art           : max channel error {bot}  "
          f"{'OK' if bot <= 12 else 'TOO HIGH'}")
    print(f"  -> {os.path.basename(OUT)}  {len(out):,} B")

    rt = Image.fromarray(decode(out))
    rt.save(os.path.join(HERE, "_bc7_roundtrip.png"))
    prev = Image.new("RGB", (W, H), (12, 10, 22))
    prev.paste(rt, (0, 0), rt)
    prev.save(os.path.join(HERE, "_bc7_roundtrip_preview.png"))


if __name__ == "__main__":
    main()
