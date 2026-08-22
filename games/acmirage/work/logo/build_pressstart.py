#!/usr/bin/env python3
"""
build_pressstart.py — put the Hebrew calligraphy into the logo the game ACTUALLY draws:
`UI_PressStart_Text_AR` (1024x560) in `DataPC_extra.forge`.

How this one was found, after `UI_TitleReveal_AR` turned out to be dead data: a
signature search (`find_logo.py`) over every texture, scoring on the SHAPE of the
artwork — wide canvas, 3 stacked full-width ink bands, line-art coverage — rather than
on the name (patch forges encrypt them) or the size (unknown). It surfaced a whole
per-language family `UI_PressStart_Text_{AR,JPN,KOR,Trad_CH,...}` with the same 3-band
proportions as the TitleReveal set.

The decisive difference is visible, not structural: TitleReveal is pure WHITE, while
PressStart is GOLD-gradient on MIRAGE and the Arabic — which is exactly what the screen
shows. So the colour has to be preserved here; flattening to white (correct for the
white artwork) would visibly change the logo.

    band 1  y   6..201   ASSASSIN'S CREED   white      (kept verbatim)
    band 2  y 232..348   M I R A G E        gold       (kept verbatim)
    band 3  y 375..540   السَّراب             gold       <-- REPLACED with מיראז'

    python build_pressstart.py            # build + preview
    python build_pressstart.py --deploy   # also write into the forge
"""
import argparse
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "tools")
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "acshadows", "tools"))

from bc7_encode import encode  # noqa: E402
from mirage_texdump import find_dims  # noqa: E402
from mirage_texture import load  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FORGE = r"F:/Game Lab/Assassin's Creed Mirage/DataPC_extra.forge"
IDS = {2181436741074: "Map_PC", 2181436741075: "MapDesc"}
W, H = 1024, 560
BAND3 = (375, 541)                    # the Arabic line, rows [start, end)
ART = os.path.join(HERE, "..", "..", "..", "..", "תמונה4.png")
SS = 3


def extract_art(path):
    """The supplied Hebrew calligraphy -> a clean alpha mask (white ink on dark)."""
    a = np.array(Image.open(path).convert("RGBA"))
    lum = a[..., :3].mean(axis=2)
    m = (((lum > 128) & (a[..., 3] > 40)) * 255).astype(np.uint8)
    ys, xs = np.where(m > 0)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()

    res, _ = load(FORGE, 2181436741074, payload_len=W * H)
    orig = np.flipud(np.array(
        Image.frombytes("RGBA", (W, H), res.pixels, "bcn", (7,)))).astype(np.int16)
    print(f"# original {W}x{H}")

    # --- measure the gold gradient of the band we are replacing ------------------
    y0, y1 = BAND3
    band = orig[y0:y1]
    solid = band[..., 3] > 200
    rows_rgb = []
    for r in range(band.shape[0]):
        sel = solid[r]
        rows_rgb.append(band[r][sel][:, :3].mean(axis=0) if sel.any() else None)
    known = [(i, c) for i, c in enumerate(rows_rgb) if c is not None]
    print(f"  gold gradient sampled over {len(known)} rows: "
          f"top {known[0][1].round(0)} -> bottom {known[-1][1].round(0)}")
    grad = np.zeros((band.shape[0], 3), np.float64)          # fill gaps by interpolation
    idx = np.array([i for i, _ in known])
    for ch in range(3):
        grad[:, ch] = np.interp(np.arange(band.shape[0]), idx,
                                np.array([c[ch] for _, c in known]))

    cols = np.where(band[..., 3].max(axis=0) > 8)[0]
    bx0, bx1 = int(cols.min()), int(cols.max())
    print(f"  band 3: rows {y0}..{y1-1} ({y1-y0} px), x {bx0}..{bx1} ({bx1-bx0+1} px)")

    # --- fit the Hebrew into that exact box --------------------------------------
    art = extract_art(ART)
    tw = bx1 - bx0 + 1
    th = max(1, round(art.shape[0] * tw / art.shape[1]))
    if th > (y1 - y0):                                        # never overflow the band
        th = y1 - y0
        tw = max(1, round(art.shape[1] * th / art.shape[0]))
    big = cv2.resize(art, (tw * SS, th * SS), interpolation=cv2.INTER_CUBIC)
    heb = cv2.resize(big, (tw, th), interpolation=cv2.INTER_AREA)
    print(f"  hebrew art {art.shape[1]}x{art.shape[0]} -> {tw}x{th}")

    out = orig.copy()
    out[y0:y1, :, 3] = 0                                      # clear the Arabic
    top = y0 + ((y1 - y0) - th) // 2
    left = bx0 + (tw_gap := ((bx1 - bx0 + 1) - tw) // 2)
    out[top:top + th, left:left + tw, 3] = heb
    # colour every texel of the band with the sampled gradient, so filtering can never
    # drag a foreign colour into the edges
    for r in range(y0, y1):
        out[r, :, :3] = grad[r - y0]
    out = out.astype(np.uint8)

    png = os.path.join(HERE, "PRESSSTART_HE.png")
    Image.fromarray(out).save(png)
    prev = Image.new("RGB", (W, H), (12, 10, 22))
    im = Image.fromarray(out)
    prev.paste(im, (0, 0), im)
    prev.save(png.replace(".png", "_preview.png"))
    print(f"  -> {os.path.basename(png)} + preview")

    # --- encode: keep every block row above the band, re-encode the rest ----------
    split = (y0 // 4) * 4                                     # block-aligned
    flipped = np.flipud(out)                                  # store order is bottom-up
    n_rows = (H - split) // 4
    enc = encode(np.ascontiguousarray(flipped[: n_rows * 4]))
    payload = enc + res.pixels[n_rows * (W // 4) * 16:]
    assert len(payload) == W * H, f"{len(payload)} != {W*H}"
    bc7 = os.path.join(HERE, "PRESSSTART_HE.bc7")
    open(bc7, "wb").write(payload)
    back = np.flipud(np.array(Image.frombytes("RGBA", (W, H), payload, "bcn", (7,))))
    keep_err = np.abs(back[:split].astype(int) - orig[:split].astype(int)).max()
    new_err = np.abs(back[split:].astype(int) - out[split:].astype(int)).max()
    print(f"  bc7 {len(payload):,} B  | rows 0..{split-1} vs original: max err {keep_err} "
          f"({'IDENTICAL' if keep_err == 0 else 'CHANGED'}) | new band max err {new_err}")

    if not a.deploy:
        print("\n(dry run — pass --deploy to write into the forge)")
        return
    py = sys.executable
    for rid, lbl in IDS.items():
        blob = os.path.join(HERE, f"_ps_{rid}.bin")
        subprocess.run([py, os.path.join(TOOLS, "mirage_texture.py"), FORGE,
                        "build", str(rid), bc7, blob], check=True)
        subprocess.run([py, os.path.join(TOOLS, "mirage_deploy.py"), FORGE,
                        "inplace", str(rid), blob], check=True)


if __name__ == "__main__":
    main()
