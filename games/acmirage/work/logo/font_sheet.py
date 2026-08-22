#!/usr/bin/env python3
"""Contact sheet of every installed Hebrew font rendering מיראז' — pick by eye, not by name."""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
F = r"C:\Windows\Fonts"
WORD = "מיראז'"

CANDIDATES = [
    "stamsefaradclm-webfont.ttf", "stamashkenazclm-webfont.ttf",
    "KtavYadCLM-BoldItalic.otf", "KtavYadCLM-MediumItalic.otf",
    "HATTEN.TTF", "Kanisah.ttf", "krashim.ttf", "takila.ttf", "tapuach.ttf",
    "levavot.ttf", "liron.ttf", "Baznat.ttf", "Dragon.ttf", "lostcity.ttf",
    "maklot_ez.ttf", "names.ttf", "Hermetica.otf", "Deco0.1.otf", "ECO.otf",
    "Asakim Bold.ttf", "Kidma-Book.ttf", "HorevCLM-Heavy.otf",
    "GladiaCLM-Bold.otf", "AnkaCLM-Bold.otf", "HillelCLM-Medium.otf",
    "DorianCLM-Book.ttf", "GanCLM-Bold.ttf", "JournalCLM-Light.otf",
    "Heebo-Medium.ttf", "Heebo-Bold.ttf", "Heebo-Regular.ttf",
    "FrankRuhlLibre-Medium.ttf", "FrankRuhlLibre-Bold.ttf",
    "DavidLibre-Medium.ttf", "Alef-bold.ttf", "Assistant-SemiBold.ttf",
    "AHROB.TTF", "nrkis.ttf", "shmuel.ttf", "rod.ttf", "tamir.ttf",
    "GveretLevinAlefAlefAlef-Regular.otf", "DanaYadAlefAlefAlef-Normal(1).otf",
    "AmaticaSC-Bold.ttf", "keteryg-bold-webfont.ttf", "shofardemi-bold-webfont.ttf",
    "nachlieliclm-boldoblique-webfont.ttf", "yehudaclm-light-webfont.ttf",
    "trashimclm-bold-webfont.ttf", "shmulikclm-webfont.ttf",
    "migdalfontwin-webfont.ttf", "paskol-webfont.ttf", "nehama-webfont.ttf",
    "makabiyg-webfont.ttf", "miriwin-webfont.ttf", "Abraham-Regular.ttf",
    "CarmelitBold.otf", "ElliniaCLM-Bold.ttf", "Dina-TalBal.otf",
    "HummusChipsSalat.ttf", "samurai_heb.ttf", "GHAIM.TTF", "GFRANK.TTF",
    "DROGB.TTF", "ANARB__.TTF", "ASHEM__.TTF", "DYBBUK_.TTF", "GAGUB__.TTF",
]

CELL_W, CELL_H, COLS = 430, 130, 3
rows = (len(CANDIDATES) + COLS - 1) // COLS
sheet = Image.new("RGB", (CELL_W * COLS, CELL_H * rows), (12, 10, 22))
d = ImageDraw.Draw(sheet)
lbl = ImageFont.truetype(os.path.join(F, "consola.ttf"), 13)

ok = 0
for i, name in enumerate(CANDIDATES):
    p = os.path.join(F, name)
    cx, cy = (i % COLS) * CELL_W, (i // COLS) * CELL_H
    if not os.path.exists(p):
        d.text((cx + 8, cy + 8), f"MISSING {name}", font=lbl, fill=(120, 60, 60))
        continue
    try:
        ft = ImageFont.truetype(p, 62)
        d.text((cx + 18, cy + 28), WORD, font=ft, fill=(255, 255, 255),
               direction="rtl", language="he")
        ok += 1
    except Exception as ex:
        try:
            ft = ImageFont.truetype(p, 62)
            d.text((cx + 18, cy + 28), WORD[::-1], font=ft, fill=(255, 255, 255))
            ok += 1
        except Exception as ex2:
            d.text((cx + 8, cy + 40), f"FAIL {type(ex2).__name__}", font=lbl, fill=(150, 70, 70))
    d.text((cx + 8, cy + 4), f"{i:02d} {name}", font=lbl, fill=(120, 150, 190))
    d.line([(cx, cy), (cx, cy + CELL_H)], fill=(40, 38, 55))
    d.line([(cx, cy), (cx + CELL_W, cy)], fill=(40, 38, 55))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "font_sheet.png")
sheet.save(out)
print(f"{ok}/{len(CANDIDATES)} rendered -> {out}  {sheet.size}")
