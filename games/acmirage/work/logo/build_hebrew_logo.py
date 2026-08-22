#!/usr/bin/env python3
"""
build_hebrew_logo.py — replace AC Mirage's Arabic line with Hebrew "מיראז'" in the
same connected, monoline, kashida-baseline style.

Measured from the shipped texture (UI_TitleReveal_AR, 1072x600 BC7):
    band 1  y   9..220   ASSASSIN'S CREED      (kept verbatim)
    band 2  y 241..372   M I R A G E (Latin)   (kept verbatim)
    band 3  y 393..567   السَّراب               <-- REPLACED
    stroke weight     13 px (median vertical run)
    kashida baseline  y 507..520 abs  (13 px — the SAME weight as the strokes)
    letter tops       y ~438 abs      (body ~69 px)
    ink span          x 12..1059      (1048 px)

Two facts decide the design, both measured rather than assumed:
  * the shipped Arabic is a MONOLINE face (uniform 13 px), not classical calligraphy,
    so the Hebrew comes from a monoline geometric face (Heebo) — measured stroke at
    the target body height: Light 7 · Regular 11 · Medium 15 · Bold 18 px. Scaling
    Heebo-Regular up to an 88 px body lands the stroke on ~14 px = the Arabic's.
  * the kashida is a DEAD-STRAIGHT bar and the letters meet it at a hard 90° junction
    (no fillets) — so a plain rectangle is the authentic join, not a curve.

Hebrew is narrower than Arabic, so the body is raised 69 -> 88 px to recover ink
density; everything else is dimensionally identical to the original.

    python build_hebrew_logo.py                 # build all variants + previews
    python build_hebrew_logo.py --variant swash
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "MIRAGE_TitleReveal_AR_original.png")
FONTS = r"C:\Windows\Fonts"
BG = (12, 10, 22)

W, H = 1072, 600
KEEP_TO = 384           # bands 1+2 end here (band-3 ink starts at 393)
BAR_TOP, BAR_BOT = 507, 519      # kashida: 13 px, == the stroke weight
LEFT, RIGHT = 12, 1059           # ink span of the original band
STROKE = 13
BODY = 88                        # letter height; puts Heebo-Regular's stem on ~14 px
BODY_TOP = BAR_TOP - BODY        # 419
FONT = "Heebo-Regular.ttf"

# how far the word spreads inside the ink span. The shipped Arabic distributes its
# letters across the WHOLE width with two long kashida stretches; a fully even spread
# reads as loose letters, so the word is spread wide but stops short of the edges and
# the bare kashida runs out to them — the same silhouette, still readable as a word.
WORD_SPAN = 0.80


def glyph(font, ch, target_h, wide=1.0):
    """One glyph, tightly cropped, scaled so its ink is exactly target_h tall.

    `wide` stretches horizontally. Arabic letterforms are far wider than Hebrew at
    the same height (the shipped ش and ب are ~160 px wide against a 69 px body), so
    a 1:1 Hebrew setting reads as sparse letters strung on a rail. Widening is also
    native to Hebrew display lettering (the square/"meruba" hand), so it buys the
    Arabic density without inventing anything foreign to the script.
    """
    probe = Image.new("L", (900, 900), 0)
    ImageDraw.Draw(probe).text((450, 450), ch, font=font, fill=255, anchor="mm")
    bb = probe.getbbox()
    if bb is None:
        return None
    g = probe.crop(bb)
    s = target_h / g.height
    return g.resize((max(1, round(g.width * s * wide)), target_h), Image.LANCZOS)


def hebrew_band(span_frac=WORD_SPAN, wide=1.0, weight=FONT, body=BODY, swash=True):
    """Render just the Hebrew line into an alpha mask (the rest of the logo is kept
    verbatim from the shipped texture)."""
    body_top = BAR_TOP - body
    a = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(a)
    d.rectangle([LEFT, BAR_TOP, RIGHT, BAR_BOT], fill=255)   # the kashida

    font = ImageFont.truetype(os.path.join(FONTS, weight), 400)

    # מיראז'  — RTL, so mem is placed first at the right.
    # The yod is a small letter that HANGS from the top line (in Hebrew it never
    # reaches the baseline) — the same way the shadda floats over the shipped ش.
    # It is therefore left unattached rather than faked into a vav-looking stem,
    # and its two gaps are tightened so it reads as part of מ־י־ר, not as debris.
    plan = [("מ", 1.00), ("י", 0.40), ("ר", 1.00), ("א", 1.00), ("ז", 1.00)]
    masks = [(ch, glyph(font, ch, max(8, round(body * f)), wide)) for ch, f in plan]
    ger = glyph(font, "׳", round(body * 0.26), wide)

    ink = sum(m.width for _, m in masks) + (ger.width if ger else 0)
    span = round((RIGHT - LEFT) * span_frac)
    x0 = LEFT + ((RIGHT - LEFT) - span) // 2                 # centred in the ink span
    # gap weights: the yod hugs its neighbours, the geresh only needs a sliver
    gaps = [1.0, 0.45, 0.45, 1.0, 0.35]
    track = (span - ink) / sum(gaps)

    x = float(x0 + span)                                     # walk right -> left
    for i, (ch, m) in enumerate(masks):
        x -= m.width
        a.paste(255, (round(x), body_top), m)                # all hang from one top line
        if ch == "ז" and ger:                                # geresh rides the zayin
            a.paste(255, (round(x - ger.width - max(4, round(6 * wide))), body_top - 2), ger)
            x -= ger.width + max(4, round(6 * wide))
        x -= track * gaps[i]

    if swash:
        _swash(d)
    return a


def build(variant="swash", out=None, **kw):
    src = Image.open(SRC).convert("RGBA")
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    canvas.paste(src.crop((0, 0, W, KEEP_TO)), (0, 0))      # bands 1+2 verbatim

    a = hebrew_band(swash=(variant == "swash"), **kw)
    heb = Image.composite(Image.new("RGBA", (W, H), (255, 255, 255, 255)),
                          Image.new("RGBA", (W, H), (255, 255, 255, 0)), a)
    canvas.alpha_composite(heb)

    out = out or os.path.join(HERE, f"MIRAGE_HE_{variant}.png")
    canvas.save(out)
    prev = Image.new("RGB", (W, H), BG)
    prev.paste(canvas, (0, 0), canvas)
    prev.save(out.replace(".png", "_preview.png"))
    print(f"  {variant:10s} -> {os.path.basename(out)}")
    return out


def compare():
    """One sheet of candidate settings — pick the design by eye, not by argument."""
    opts = [
        ("A  span.80 w1.0  Regular", dict(span_frac=0.80, wide=1.00, weight="Heebo-Regular.ttf")),
        ("B  span.62 w1.0  Regular", dict(span_frac=0.62, wide=1.00, weight="Heebo-Regular.ttf")),
        ("C  span.80 w1.35 Light",   dict(span_frac=0.80, wide=1.35, weight="Heebo-Light.ttf")),
        ("D  span.92 w1.35 Light",   dict(span_frac=0.92, wide=1.35, weight="Heebo-Light.ttf")),
        ("E  span.72 w1.20 Regular", dict(span_frac=0.72, wide=1.20, weight="Heebo-Regular.ttf")),
        ("F  span.92 w1.55 Light",   dict(span_frac=0.92, wide=1.55, weight="Heebo-Light.ttf")),
    ]
    src = Image.open(SRC).convert("RGBA")
    ref = Image.new("RGB", (W, 190), BG)
    ref.paste(src.crop((0, 385, W, 575)), (0, 0), src.crop((0, 385, W, 575)))
    sheet = Image.new("RGB", (W, 190 * (len(opts) + 1)), BG)
    sheet.paste(ref, (0, 0))
    lbl = ImageFont.truetype(os.path.join(FONTS, "consola.ttf"), 15)
    ImageDraw.Draw(sheet).text((10, 6), "ORIGINAL ARABIC (target)", font=lbl, fill=(110, 170, 220))
    for i, (name, kw) in enumerate(opts):
        a = hebrew_band(**kw)
        row = Image.new("RGB", (W, 190), BG)
        m = a.crop((0, 385, W, 575))
        row.paste((255, 255, 255), (0, 0), m)
        sheet.paste(row, (0, 190 * (i + 1)))
        ImageDraw.Draw(sheet).text((10, 190 * (i + 1) + 6), name, font=lbl, fill=(110, 170, 220))
    p = os.path.join(HERE, "_compare.png")
    sheet.save(p)
    print(f"  compare -> {p}")


def _swash(d):
    """The tail that leaves the kashida and sweeps down-left — the ب of السراب.

    Drawn as a filled polygon rather than a stroked polyline: PIL's `line` with
    joint="curve" leaves gaps at this width, which is what made the first attempt
    render as a dotted arc.
    """
    x_end = LEFT + 236
    top, bot = [], []
    for t in range(0, 121):
        u = t / 120
        x = x_end - 224 * u
        y = BAR_BOT + 52 * math.sin(math.pi * u * 0.88)
        # taper the tail slightly as it runs out, like a pen lifting
        w = STROKE * (1.0 - 0.18 * u)
        top.append((x, y - w / 2))
        bot.append((x, y + w / 2))
    d.polygon(top + bot[::-1], fill=255)
    cx, cy = LEFT + 96, BAR_BOT + 46
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=255)     # the nuqta under the tail


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=None)
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    print(f"# {os.path.basename(SRC)} {W}x{H} · bar {BAR_TOP}..{BAR_BOT} · body {BODY}")
    if a.compare:
        compare()
    else:
        for v in ([a.variant] if a.variant else ["connected", "swash"]):
            build(v)
