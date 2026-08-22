#!/usr/bin/env python3
"""
fit_user_art.py — take the supplied Hebrew calligraphy (מיראז' drawn in the Arabic
manner) and fit it into AC Mirage's title texture in place of the shipped السَّراب.

The supplied art is white-on-white: the strokes are pure white and only a soft grey
emboss (~239-246) marks their edges, so a plain luminance threshold returns the
OUTLINE, not the shape. The extraction therefore seals that outline and flood-fills
from the border, which recovers the solid glyph instead of a hollow one.

Target geometry, measured from the shipped texture (UI_TitleReveal_AR, 1072x600 BC7):
    band 1  y   9..220   ASSASSIN'S CREED     (kept verbatim)
    band 2  y 241..372   M I R A G E          (kept verbatim)
    band 3  y 393..567   the Arabic line      <-- replaced
    ink span x 12..1059  (1048 px)

    python fit_user_art.py [--src <png>] [--pad 0]
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "MIRAGE_TitleReveal_AR_original.png")
DEFAULT_ART = r"C:\Users\Nehoray_Cohen\Downloads\Gemini_Generated_Image_ozfu7wozfu7wozfu.png"
BG = (12, 10, 22)

W, H = 1072, 600
KEEP_TO = 384                    # bands 1+2 end here
LEFT, RIGHT = 12, 1059           # ink span of the original band
BAND_TOP, BAND_BOT = 393, 567    # the Arabic line's vertical extent
SS = 3                           # render the art this much larger, then downsample


def extract(path):
    """Solid alpha for the supplied line art.

    Two shapes of source have come through, so both are handled rather than assumed:
      * white strokes on a dark/transparent ground -> the ink IS the mask
      * white strokes on a WHITE ground, where only a soft grey emboss (~239-246)
        marks the edges -> a luminance threshold returns the OUTLINE, so the outline
        is sealed and the border flood-filled to recover a solid glyph
    Picking the wrong one silently yields hollow letters, so the branch is decided by
    measuring how much genuinely-dark ground the image has.
    """
    im = Image.open(path).convert("RGBA")
    a = np.array(im)
    lum = a[..., :3].mean(axis=2)
    alpha = a[..., 3]
    dark_ground = (lum < 100).mean()

    if dark_ground > 0.05:                                  # white-on-dark
        return (((lum > 128) & (alpha > 40)) * 255).astype(np.uint8)

    edge = (lum < 251).astype(np.uint8)                     # the grey emboss
    # seal hairline breaks in the outline so the fill cannot leak through them
    edge = cv2.morphologyEx(edge, cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    h, w = edge.shape
    ff = edge.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 2)                      # paint the outside
    solid = (ff != 2).astype(np.uint8)                      # everything not outside
    n, lab, stats, _ = cv2.connectedComponentsWithStats(solid, 8)
    keep = np.zeros_like(solid)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 400:               # drop emboss specks
            keep[lab == i] = 1
    return (keep * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_ART)
    ap.add_argument("--pad", type=int, default=0,
                    help="shrink the art this many px inside the ink span")
    a = ap.parse_args()

    art = extract(a.src)
    ys, xs = np.where(art > 0)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    art = art[y0:y1 + 1, x0:x1 + 1]
    sh, sw = art.shape
    print(f"# art {os.path.basename(a.src)}  ink {sw}x{sh}")

    # scale to the shipped ink span; the height follows so nothing is distorted
    span = (RIGHT - LEFT) - 2 * a.pad
    scale = span / sw
    tw, th = span, max(1, round(sh * scale))
    big = cv2.resize(art, (tw * SS, th * SS), interpolation=cv2.INTER_CUBIC)
    band = cv2.resize(big, (tw, th), interpolation=cv2.INTER_AREA)   # clean edges

    # centre on the Arabic line's own vertical centre so the block sits where the
    # original sat, whatever the art's aspect turned out to be
    cy = (BAND_TOP + BAND_BOT) // 2
    top = cy - th // 2
    if top + th > H:
        top = H - th
    top = max(KEEP_TO + 1, top)
    print(f"# fitted {tw}x{th} at x={LEFT + a.pad} y={top}  (scale {scale:.4f})")

    alpha = np.zeros((H, W), np.uint8)
    alpha[top:top + th, LEFT + a.pad:LEFT + a.pad + tw] = band

    # measure what the scaling did to the pen — the shipped face is 13 px monoline
    runs = []
    for x in range(0, W, 2):
        c = 0
        for v in alpha[:, x] > 128:
            if v:
                c += 1
            elif c:
                runs.append(c)
                c = 0
        if c:
            runs.append(c)
    if runs:
        print(f"# resulting stroke: median {np.median(runs):.0f} px  (shipped Arabic: 13)")

    src = Image.open(LOGO).convert("RGBA")
    full = np.zeros((H, W, 4), np.uint8)
    # Bands 1+2 are copied with their RGB INTACT. Measured on the shipped texture:
    # 298,715 texels sit at alpha 1..199 carrying near-black RGB (mean 18) — that is
    # not encoder debris, it is a soft shadow baked into the artwork. Flattening it to
    # white lights it up as a halo around ASSASSIN'S CREED.
    full[:KEEP_TO] = np.array(src.crop((0, 0, W, KEEP_TO)))
    # The new Hebrew line has no baked shadow, so its RGB is pure white throughout —
    # which also makes every one of its blocks collinear in RGBA space (only alpha
    # varies), the condition a single-axis BC7 mode needs to be near-lossless.
    hb = alpha[KEEP_TO:] > 0
    full[KEEP_TO:][..., 3] = alpha[KEEP_TO:]
    full[KEEP_TO:][..., :3] = 255

    canvas = Image.fromarray(full)
    out = os.path.join(HERE, "MIRAGE_HE_final.png")
    canvas.save(out)
    prev = Image.new("RGB", (W, H), BG)
    prev.paste(canvas, (0, 0), canvas)
    prev.save(os.path.join(HERE, "MIRAGE_HE_final_preview.png"))

    # the two lines stacked, so the Hebrew can be judged against the Arabic it replaces
    cmp_ = Image.new("RGB", (W, 400), BG)
    o = src.crop((0, 385, W, 585))
    cmp_.paste((255, 255, 255), (0, 0), o.getchannel("A"))
    cmp_.paste((255, 255, 255), (0, 200), Image.fromarray(alpha).crop((0, 385, W, 585)))
    cmp_.save(os.path.join(HERE, "_compare_final.png"))
    print("  -> MIRAGE_HE_final.png + _preview + _compare_final.png")


if __name__ == "__main__":
    main()
