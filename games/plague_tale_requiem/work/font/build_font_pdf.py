#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_font_pdf.py — render a comparison PDF of period-appropriate Hebrew fonts for
A Plague Tale: Requiem (1349 medieval France / plague). Each candidate is shown on a
parchment card (matching the game's misty menu) with real in-game strings, numbered
so the user can pick one. Chosen font -> rebuild the atlas:
    python build_hebrew_font.py --font "<path>" --deploy
"""
from __future__ import annotations
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from bidi.algorithm import get_display

WF = r"C:\Windows\Fonts"
HERE = os.path.dirname(os.path.abspath(__file__))
DL = os.path.join(HERE, "fonts_pdf")
OUT = os.path.join(HERE, "PLAGUE_TALE_hebrew_fonts.pdf")

# (path, Latin name, Hebrew tag/vibe)  — curated, best period fit first
CANDS = [
    (f"{WF}\\VILNAB.TTF",              "Guttman Vilna Bold", "דפוס וילנא קלאסי — הכי תקופתי"),
    (f"{DL}\\SuezOne-Regular.ttf",     "Suez One",           "כבד בסגנון דפוס עתיק"),
    (f"{WF}\\FRANKB.TTF",              "Frank Ruehl Bold",   "ספר מסורתי (הנוכחי במשחק)"),
    (f"{WF}\\frank.ttf",               "FrankRuehl",         "פרנק-ריהל קלאסי, רזה יותר"),
    (f"{DL}\\DavidLibre-Bold.ttf",     "David Libre Bold",   "דויד אלגנטי ומעודן"),
    (f"{DL}\\Bellefair-Regular.ttf",   "Bellefair",          "אות דקה ואצילית"),
    (f"{DL}\\FrankRuhlLibre.ttf",      "Frank Ruhl Libre",   "פרנק-ריהל מודרני מלוטש"),
    (f"{WF}\\nrkis.ttf",               "Narkisim",           "נרקיסים מסורתי"),
    (f"{DL}\\Tinos-Regular.ttf",       "Tinos",              "קלאסי בנוסח טיימס"),
    (f"{WF}\\davidbd.ttf",             "David Bold",         "דויד עבה (Windows)"),
    (f"{WF}\\rod.ttf",                 "Rod",                "כתב-יד — תחושת מגילה"),
    (f"{WF}\\mriam.ttf",               "Miriam",             "מרים נקייה וקריאה"),
]

# real in-game strings + alphabet + a plague-era sentence
L_TITLE   = "תחת שמש חדשה"
L_MENU    = "המשך · הגדרות · מסע ארוך · יציאה"
L_ALEF    = "א ב ג ד ה ו ז ח ט י כ ך ל מ ם נ ן ס ע פ ף צ ץ ק ר ש ת"
L_SENT    = "העכברושים מציפים את הממלכה; אמיסיה ויוגו נמלטים בין הצללים."

W, H = 1654, 2339                  # A4 @ ~200 dpi
MARGIN = 70
PARCH = (232, 227, 216)           # misty parchment
INK   = (43, 36, 27)              # dark brown ink
INK2  = (96, 84, 66)             # subtle ink
ACCENT = (150, 120, 40)          # muted gold


def rtl(s):
    return get_display(s)


def parchment_page():
    # soft vignette parchment like the game's menu
    base = Image.new("RGB", (W, H), PARCH)
    vig = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(vig)
    d.ellipse([-W * 0.25, -H * 0.15, W * 1.25, H * 1.15], fill=40)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGB", (W, H), (205, 198, 184))
    base = Image.composite(base, dark, vig)
    # faint noise
    n = (np.random.default_rng(7).integers(0, 10, (H, W, 1)).repeat(3, 2)).astype(np.uint8)
    base = Image.fromarray(np.clip(np.array(base).astype(int) - n + 4, 0, 255).astype(np.uint8))
    return base


def font(path, size):
    return ImageFont.truetype(path, size)


def draw_rtl(d, xy_right, s, fnt, fill):
    """draw s so its RIGHT edge is at xy_right[0] (RTL alignment)."""
    disp = rtl(s)
    w = d.textlength(disp, font=fnt)
    d.text((xy_right[0] - w, xy_right[1]), disp, font=fnt, fill=fill)
    return w


def main():
    cands = [(p, n, t) for (p, n, t) in CANDS if os.path.exists(p)]
    print(f"{len(cands)} fonts")
    pages = []

    # header font (use Frank Ruehl Bold for UI chrome)
    hdr = font(f"{WF}\\FRANKB.TTF", 76)
    sub = font(f"{WF}\\FRANKB.TTF", 34)
    lat = font(f"{WF}\\segoeuib.ttf", 30)
    latn = font(f"{WF}\\segoeui.ttf", 26)
    num_f = font(f"{WF}\\FRANKB.TTF", 60)

    per_page = 3
    card_h = (H - 260) // per_page
    idx = 0
    for pi in range((len(cands) + per_page - 1) // per_page):
        pg = parchment_page()
        d = ImageDraw.Draw(pg)
        # page header
        if pi == 0:
            draw_rtl(d, (W - MARGIN, 60), "גופנים עבריים לבחירה", hdr, INK)
            d.text((MARGIN, 90), "A Plague Tale: Requiem", font=lat, fill=INK2)
            draw_rtl(d, (W - MARGIN, 170), "בחר מספר — אבנה מחדש את האטלס עם הגופן שתבחר", sub, INK2)
            d.line([(MARGIN, 225), (W - MARGIN, 225)], fill=ACCENT, width=3)
            top0 = 260
        else:
            draw_rtl(d, (W - MARGIN, 60), f"גופנים עבריים לבחירה — עמ' {pi+1}", sub, INK2)
            d.line([(MARGIN, 120), (W - MARGIN, 120)], fill=ACCENT, width=2)
            top0 = 150

        for row in range(per_page):
            if idx >= len(cands):
                break
            path, name, tag = cands[idx]
            y = top0 + row * card_h
            # card frame
            d.rounded_rectangle([MARGIN, y, W - MARGIN, y + card_h - 30], radius=14,
                                outline=(180, 170, 150), width=2)
            # number badge
            d.rounded_rectangle([MARGIN + 18, y + 22, MARGIN + 92, y + 96], radius=10,
                                fill=ACCENT)
            nb = str(idx + 1)
            wnb = d.textlength(nb, font=num_f)
            d.text((MARGIN + 55 - wnb / 2, y + 24), nb, font=num_f, fill=(250, 246, 236))
            # name + tag (RTL tag on the right, Latin name under it)
            draw_rtl(d, (W - MARGIN - 24, y + 24), tag, sub, INK)
            nmw = d.textlength(name, font=lat)
            d.text((W - MARGIN - 24 - nmw, y + 74), name, font=lat, fill=INK2)

            try:
                f_title = font(path, 96)
                f_menu  = font(path, 52)
                f_alef  = font(path, 46)
                f_sent  = font(path, 46)
            except Exception as e:
                d.text((MARGIN + 120, y + 40), f"[load fail] {e}", font=latn, fill=(150, 40, 40))
                idx += 1
                continue

            yy = y + 120
            draw_rtl(d, (W - MARGIN - 30, yy), L_TITLE, f_title, INK)
            yy += 120
            draw_rtl(d, (W - MARGIN - 30, yy), L_MENU, f_menu, INK)
            yy += 72
            draw_rtl(d, (W - MARGIN - 30, yy), L_ALEF, f_alef, INK2)
            yy += 66
            draw_rtl(d, (W - MARGIN - 30, yy), L_SENT, f_sent, INK)
            idx += 1

        pages.append(pg)

    # PDF: avoid PIL's JPEG path (libjpeg not registered here) -> palette mode = Flate
    pp = [p.convert("P", palette=Image.ADAPTIVE, colors=256) for p in pages]
    pp[0].save(OUT, save_all=True, append_images=pp[1:], resolution=200.0)
    print("wrote", OUT, f"({len(pages)} pages)")
    # also a PNG of page 1 for quick inline preview
    prev = os.path.join(HERE, "_font_pdf_p1.png")
    pages[0].save(prev)
    print("preview", prev)


if __name__ == "__main__":
    main()
