# -*- coding: utf-8 -*-
"""THE SIZE LEVER, measured instead of guessed.

The engine scales a LINE so its tallest declared BOX fits the requested row height:
        screen_ink = REQUESTED x ink_h / max(box_h in the line)
(Proved by elimination: three builds with tight boxes at em 18/29/36 ALL rendered ~30 px,
which only happens if the normaliser is the tallest box among the glyphs actually drawn.)

For a CONSISTENT size line-to-line every Hebrew box must be the same height, and that height
must cover the full vertical span lamed-top .. deepest-descender.  So the on-screen size of an
ordinary letter is fixed by ONE property of the typeface:

        screen(nun) = REQUESTED x  body_ink / (max_ascent + max_descent)

i.e. a typeface with a modest lamed and short descenders renders BIGGER at the same
consistency.  This ranks every Hebrew-capable font on the machine by exactly that ratio,
plus the stroke weight (the game's own Arabic sits at ~5.5% of the body).
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HEB = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
BODY = 40.0                     # reference body (mem) height in px
REQ = 30.0                      # requested row height the engine asks for (measured in-game)


def fit_body(path, target):
    for s in range(8, target * 4):
        try:
            f = ImageFont.truetype(path, s)
        except Exception:
            return None
        b = f.getbbox("מ")
        if b and (b[3] - b[1]) >= target:
            return f
    return None


def stroke_ratio(font, body):
    """median horizontal run length of ink in the middle band of a few letters / body."""
    runs = []
    for ch in "נהחת":
        b = font.getbbox(ch)
        if not b:
            continue
        w, h = b[2] - b[0] + 8, b[3] - b[1] + 8
        img = Image.new("L", (max(w, 8), max(h, 8)), 0)
        ImageDraw.Draw(img).text((4 - b[0], 4 - b[1]), ch, 255, font=font)
        a = np.array(img)
        ys = np.where(a.max(axis=1) > 100)[0]
        if len(ys) < 4:
            continue
        for y in ys[len(ys) // 3: 2 * len(ys) // 3]:
            row = a[y] > 100
            n = 0
            for v in row:
                if v:
                    n += 1
                elif n:
                    runs.append(n); n = 0
            if n:
                runs.append(n)
    return (float(np.median(runs)) / body) if runs else 0.0


def has_hebrew(path):
    """REAL coverage: every Hebrew letter must be in the cmap AND map to a non-empty glyph.
    Without this, a Latin-only font renders 27 identical .notdef boxes -> a perfect (fake)
    ratio of 1.000, which is exactly how a font with no Hebrew tops the ranking."""
    from fontTools.ttLib import TTFont
    try:
        t = TTFont(path, fontNumber=0, lazy=True)
        cm = t.getBestCmap()
        gs = t.getGlyphSet()
        names = set()
        for cp in range(0x05D0, 0x05EB):
            g = cm.get(cp)
            if g is None:
                t.close(); return False
            names.add(g)
        t.close()
        return len(names) >= 20        # distinct outlines, not one shared box
    except Exception:
        return False


def measure(path):
    if not has_hebrew(path):
        return None
    f = fit_body(path, int(BODY))
    if f is None:
        return None
    try:
        asc_m, _desc_m = f.getmetrics()
    except Exception:
        return None
    A, D = [], []
    for ch in HEB:
        b = f.getbbox(ch)
        if not b or b[3] <= b[1]:
            return None
        A.append(asc_m - b[1])          # ink height above the baseline
        D.append(b[3] - asc_m)          # ink depth below the baseline
    body = asc_m - f.getbbox("מ")[1]
    nun = asc_m - f.getbbox("נ")[1]
    lam = max(A)
    dsc = max(D)
    span = lam + max(dsc, 0)
    if span <= 0 or body <= 0:
        return None
    return dict(body=body, nun=nun, lamed=lam, desc=dsc, span=span,
                ratio=body / span, screen=REQ * body / span,
                lam_over_body=lam / body, desc_over_body=max(dsc, 0) / body,
                stroke=stroke_ratio(f, body))


def main():
    paths = sorted(set(glob.glob(r"C:\Windows\Fonts\*.ttf") + glob.glob(r"C:\Windows\Fonts\*.otf")))
    rows = []
    for p in paths:
        try:
            r = measure(p)
        except Exception:
            r = None
        if r:
            r["name"] = os.path.basename(p)
            r["path"] = p
            rows.append(r)
    print(f"Hebrew-complete fonts measured: {len(rows)}   (body={BODY:.0f}px, REQ={REQ:.0f}px)")
    print(f"{'font':<44} {'nun':>4} {'lam':>4} {'dsc':>4} {'span':>5} {'ratio':>6} "
          f"{'screen':>7} {'lam/body':>9} {'stroke':>7}")
    for r in sorted(rows, key=lambda r: -r["ratio"])[:45]:
        print(f"{r['name']:<44} {r['nun']:>4.0f} {r['lamed']:>4.0f} {r['desc']:>4.0f} "
              f"{r['span']:>5.0f} {r['ratio']:>6.3f} {r['screen']:>7.1f} "
              f"{r['lam_over_body']:>9.2f} {r['stroke']:>7.3f}")
    cur = [r for r in rows if "opensanshebrew-light" in r["name"]]
    if cur:
        r = cur[0]
        rank = sorted(rows, key=lambda x: -x["ratio"]).index(r) + 1
        print(f"\nCURRENT ({r['name']}): ratio={r['ratio']:.3f} screen={r['screen']:.1f}px "
              f"lam/body={r['lam_over_body']:.2f} desc/body={r['desc_over_body']:.2f} "
              f"stroke={r['stroke']:.3f}   rank {rank}/{len(rows)}")


main()
