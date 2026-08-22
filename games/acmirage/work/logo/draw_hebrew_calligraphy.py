#!/usr/bin/env python3
"""
draw_hebrew_calligraphy.py — the Hebrew word מיראז' DRAWN as calligraphic pen strokes
in the manner of the Arabic line AC Mirage ships, not typeset from a Latin-style
Hebrew font with a rule underneath.

Why the letters are drawn and not typeset
-----------------------------------------
The shipped السَّراب is a single continuous reed-pen gesture: every letter enters on
the baseline, does its shape, and leaves on the baseline, so the horizontal join is
part of the LETTER, not a rail laid beneath it. Setting Heebo (or any text face) and
adding a bar underneath reproduces the silhouette and none of the logic — the letters
sit ON a line instead of flowing THROUGH it.

So each Hebrew letter here is defined as a stroke path with an explicit entry and exit
on the baseline, drawn with the same pen width as the connecting stroke. Curves are
sampled Béziers, terminals are flared the way the shipped ا and ل are, and the joins
are hard 90° like the original (measured: the shipped face has no fillets).

Measured from the shipped texture (UI_TitleReveal_AR, 1072x600 BC7):
    band 3   y 393..567    the Arabic line     <-- what we replace
    pen      13 px         (median vertical run — the face is monoline)
    baseline y 507..519    (13 px, i.e. the pen itself laid horizontally)
    body     ~69 px above the baseline, tail to ~560 below
    ink span x 12..1059

    python draw_hebrew_calligraphy.py
"""
import argparse

import os
import sys

from PIL import Image, ImageDraw

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "MIRAGE_TitleReveal_AR_original.png")
BG = (12, 10, 22)

W, H = 1072, 600
KEEP_TO = 384                 # bands 1+2 (ASSASSIN'S CREED / M I R A G E) end here
BASE = 513                    # centre of the connecting stroke
PEN = 13                      # measured stroke weight
BODY = 78                     # letter height above the baseline (Arabic: 69)
LEFT, RIGHT = 12, 1059        # ink span of the original band
SS = 4                        # supersample


# --------------------------------------------------------------------- geometry
def qbez(p0, p1, p2, n=26):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def cbez(p0, p1, p2, p3, n=34):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out


class Pen:
    """A monoline pen. PIL's `line(joint='curve')` tears at this width, so every
    segment is drawn as a thick line and every vertex capped with a disc — that gives
    genuine round joins with no gaps."""

    def __init__(self, draw, width):
        self.d = draw
        self.w = width

    def stroke(self, pts, width=None):
        w = width or self.w
        if len(pts) < 2:
            return
        self.d.line([(round(x), round(y)) for x, y in pts], fill=255, width=int(round(w)))
        r = w / 2
        for x, y in pts:
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=255)

    def taper(self, pts, w0, w1):
        """A stroke whose weight walks from w0 to w1 — used for the flared terminals
        the shipped ا and ل have, and for the tail that runs out of the word."""
        n = len(pts)
        for i in range(n - 1):
            t = i / max(1, n - 2)
            w = w0 + (w1 - w0) * t
            r = w / 2
            x, y = pts[i]
            self.d.line([(round(pts[i][0]), round(pts[i][1])),
                         (round(pts[i + 1][0]), round(pts[i + 1][1]))],
                        fill=255, width=max(1, int(round(w))))
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=255)


# --------------------------------------------------------------------- letters
# Each letter is a function of (pen, x_right, base_y, body) that draws itself with its
# foot ON the baseline and returns its advance width. Coordinates are absolute so the
# shapes can be tuned against the measured original directly.
#
# Hebrew hangs from a top line and Arabic hangs off a baseline; these forms keep the
# Hebrew skeleton (so the word stays legible) but take Arabic's stroke logic — enter
# low, rise, turn, and come back down to the line.

# Hebrew letters are narrow at a given height and Arabic ones are wide — the
# shipped ش and ب run ~160 px against a 69 px body. Drawing (rather than typesetting)
# lets the forms be widened to that proportion without the stems fattening with them,
# so the line keeps its monoline character AND the Arabic's density. The wide square
# hand ("meruba") is native Hebrew display lettering, so nothing foreign is invented.

def letter_mem(p, xr, base, b):
    """מ — right stem, shoulder, long head, left stem, and the in-turn along the line
    that closes the counter. Its two feet sit ON the connecting stroke."""
    w = b * 1.75
    xl = xr - w
    top = base - b
    r = b * 0.30
    pts = [(xr, base)]                                          # right foot on the line
    pts += [(xr, top + r)]
    pts += qbez((xr, top + r), (xr, top), (xr - r, top))        # shoulder
    pts += [(xl + r, top)]                                      # the head
    pts += qbez((xl + r, top), (xl, top), (xl, top + r))        # left turn
    pts += [(xl, base - b * 0.34)]
    pts += cbez((xl, base - b * 0.34), (xl, base - b * 0.04),
                (xl + b * 0.26, base), (xl + b * 0.62, base))   # the in-turn, onto the line
    p.stroke(pts)
    p.taper([(xr - b * 0.05, top), (xr - r * 0.6, top)], PEN, PEN * 1.35)
    return w


def letter_yod(p, xr, base, b):
    """י — the one letter that never reaches the line in Hebrew, so it is left hanging
    from the head line exactly as the shipped shadda hangs over the ش. Faking a stem
    down to the baseline turns it into a vav and costs the word its legibility."""
    w = b * 0.52
    top = base - b
    # a wedge head with a short flick down-left — a reed-pen yod, not a dot
    p.taper([(xr, top), (xr - w * 0.55, top + b * 0.06)], PEN * 1.45, PEN * 1.05)
    p.taper([(xr - w * 0.48, top + b * 0.04), (xr - w * 0.72, top + b * 0.40)],
            PEN * 1.05, PEN * 0.62)
    return w


def letter_resh(p, xr, base, b):
    """ר — right stem to the line, hard shoulder, long head ending free in the air.
    Resh has no left foot; the connecting stroke simply carries on beneath it."""
    w = b * 1.55
    xl = xr - w
    top = base - b
    r = b * 0.30
    pts = [(xr, base)]
    pts += [(xr, top + r)]
    pts += qbez((xr, top + r), (xr, top), (xr - r, top))        # shoulder
    pts += [(xl + b * 0.10, top)]
    p.stroke(pts)
    p.taper([(xl + b * 0.10, top), (xl, top)], PEN, PEN * 1.6)  # flared free terminal
    return w


def letter_alef(p, xr, base, b):
    """א — a diagonal spine with a short arm hanging off its upper left and another
    rising from its lower right. The arms are deliberately SHORT and shallower than
    the spine: run them the full width at the spine's angle and the letter collapses
    into an X."""
    w = b * 1.45
    xl = xr - w
    top = base - b
    # spine, upper-right -> lower-left, landing on the connecting stroke
    p.stroke(cbez((xr - w * 0.10, top),
                  (xr - w * 0.34, top + b * 0.30),
                  (xl + w * 0.32, base - b * 0.32),
                  (xl + w * 0.08, base)))
    # upper-left arm: hangs down-right and meets the spine above centre
    p.stroke(cbez((xl, top + b * 0.06),
                  (xl + w * 0.10, top + b * 0.22),
                  (xl + w * 0.20, top + b * 0.26),
                  (xl + w * 0.33, top + b * 0.40)))
    # lower-right arm: rises up-left and meets the spine below centre
    p.stroke(cbez((xr, base - b * 0.06),
                  (xr - w * 0.10, base - b * 0.22),
                  (xr - w * 0.20, base - b * 0.26),
                  (xr - w * 0.33, base - b * 0.40)))
    return w


def letter_zayin(p, xr, base, b):
    """ז — a head bar with the leg dropped from its CENTRE. The leg's position is the
    whole difference between ז and ד/ר, so it is placed dead centre and kept straight."""
    w = b * 1.18
    xl = xr - w
    top = base - b
    cx = xl + w * 0.50
    p.stroke([(xr, top), (xl, top)])                            # the head
    p.taper([(xr - b * 0.10, top), (xr, top)], PEN, PEN * 1.6)  # flared right terminal
    p.stroke(qbez((cx + b * 0.10, top + b * 0.02), (cx, top + b * 0.20), (cx, base)))
    return w


def geresh(p, xr, base, b):
    """׳ — the mark that makes מיראז into מיראז'; a short pen flick above the head."""
    top = base - b
    p.taper([(xr, top - b * 0.30), (xr - b * 0.15, top - b * 0.04)], PEN * 1.25, PEN * 0.6)
    return b * 0.18


LETTERS = [letter_mem, letter_yod, letter_resh, letter_alef, letter_zayin]
ASPECT = [1.75, 0.52, 1.55, 1.45, 1.18]


# --------------------------------------------------------------------- the line
def draw_band(body=BODY, span_frac=0.94, tail=True):
    a = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(a)
    p = Pen(d, PEN * SS)
    base = BASE * SS
    b = body * SS

    # the connecting stroke — the pen laid flat. It is the same weight as every
    # letter stroke, which is what makes the line read as ONE gesture.
    p.stroke([(LEFT * SS, base), (RIGHT * SS, base)])

    widths = [b * asp for asp in ASPECT]
    gw = geresh(Pen(ImageDraw.Draw(Image.new("L", (1, 1))), 1), 0, 0, b)  # advance only
    span = (RIGHT - LEFT) * SS * span_frac
    x0 = LEFT * SS + ((RIGHT - LEFT) * SS - span) / 2
    # the yod hugs its neighbours; the rest share the kashida stretch evenly
    gaps = [1.0, 0.42, 0.42, 1.0]
    track = (span - sum(widths) - gw) / sum(gaps)

    x = x0 + span
    for i, fn in enumerate(LETTERS):
        used = fn(p, x, base, b)
        x -= used
        if fn is letter_zayin:
            x -= b * 0.10
            geresh(p, x, base, b)
            x -= gw
        if i < len(gaps):
            x -= track * gaps[i]

    if tail:
        _tail(p, x0, base, b)
    return a.resize((W, H), Image.LANCZOS)


def _tail(p, x0, base, b):
    """The stroke runs out of the word and swings below the line, the way the shipped
    ب closes السراب. It leaves the connecting stroke rather than sitting apart from it."""
    x_from = LEFT * SS + b * 2.1
    pts = cbez((x_from, base),
               (x_from - b * 0.75, base + b * 0.62),
               (LEFT * SS + b * 0.85, base + b * 0.60),
               (LEFT * SS + b * 0.30, base + b * 0.14))
    p.taper(pts, PEN * SS, PEN * SS * 0.55)


# --------------------------------------------------------------------- output
def build(out=None, **kw):
    src = Image.open(SRC).convert("RGBA")
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    canvas.paste(src.crop((0, 0, W, KEEP_TO)), (0, 0))          # bands 1+2 verbatim
    a = draw_band(**kw)
    canvas.alpha_composite(Image.composite(
        Image.new("RGBA", (W, H), (255, 255, 255, 255)),
        Image.new("RGBA", (W, H), (255, 255, 255, 0)), a))

    out = out or os.path.join(HERE, "MIRAGE_HE_calligraphy.png")
    canvas.save(out)
    prev = Image.new("RGB", (W, H), BG)
    prev.paste(canvas, (0, 0), canvas)
    prev.save(out.replace(".png", "_preview.png"))

    # side-by-side against the shipped Arabic, so the two can be judged together
    cmp_ = Image.new("RGB", (W, 400), BG)
    o = src.crop((0, 385, W, 585))
    cmp_.paste((255, 255, 255), (0, 0), o.getchannel("A"))
    cmp_.paste((255, 255, 255), (0, 200), a.crop((0, 385, W, 585)))
    cmp_.save(os.path.join(HERE, "_compare_calligraphy.png"))
    print(f"  -> {os.path.basename(out)} + preview + _compare_calligraphy.png")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", type=int, default=BODY)
    ap.add_argument("--span", type=float, default=0.94)
    a = ap.parse_args()
    print(f"# pen={PEN} baseline={BASE} body={a.body} span={a.span}")
    build(body=a.body, span_frac=a.span)
