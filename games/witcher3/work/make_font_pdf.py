# -*- coding: utf-8 -*-
"""Render a PDF of curated Hebrew fonts (samples) for choosing the Witcher 3 UI font.
Run with the repo .venv python (needs Pillow + python-bidi)."""
import os, zlib
from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display


def write_pdf(images, path):
    """Pure-Python PDF: each RGB PIL image = one page, embedded as a FlateDecode image XObject.
    No JPEG / no external deps."""
    objs = []  # list of raw bytes bodies (object N = index N-1)

    def add(body):
        objs.append(body)
        return len(objs)

    catalog = add(b"")            # 1
    pages = add(b"")              # 2
    kids = []
    for im in images:
        w, h = im.size
        raw = zlib.compress(im.convert("RGB").tobytes(), 9)
        img_obj = add(
            (f"<</Type/XObject/Subtype/Image/Width {w}/Height {h}/ColorSpace/DeviceRGB"
             f"/BitsPerComponent 8/Filter/FlateDecode/Length {len(raw)}>>\nstream\n").encode()
            + raw + b"\nendstream")
        content = f"q {w} 0 0 {h} 0 0 cm /Im0 Do Q".encode()
        cs = zlib.compress(content, 9)
        cont_obj = add(f"<</Filter/FlateDecode/Length {len(cs)}>>\nstream\n".encode() + cs + b"\nendstream")
        page_obj = add((f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 {w} {h}]"
                        f"/Resources<</XObject<</Im0 {img_obj} 0 R>>>>/Contents {cont_obj} 0 R>>").encode())
        kids.append(page_obj)
    objs[catalog - 1] = b"<</Type/Catalog/Pages 2 0 R>>"
    objs[pages - 1] = ("<</Type/Pages/Kids[" + " ".join(f"{k} 0 R" for k in kids) +
                       f"]/Count {len(kids)}>>").encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<</Size {len(objs)+1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF").encode()
    with open(path, "wb") as f:
        f.write(out)

FDIR = r"C:\Windows\Fonts"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "witcher3_hebrew_fonts.pdf")

# curated set: (file, display name, hebrew category note)
FONTS = [
    ("david.ttf",   "David",                "סריף קלאסי — קריא ומכובד"),
    ("frank.ttf",   "Frank Ruehl",          "סריף קלאסי — תואם-תקופה (GoWR/Anno)"),
    ("GFRANK.TTF",  "Guttman Frank-Ruehl",  "סריף קלאסי, מעט מעוטר"),
    ("HADASAH.TTF", "Hadassah",             "סריף ספרותי חם — 'ספר עתיק'"),
    ("VILNA.TTF",   "Guttman Vilna",        "סריף מסורתי — כרוניקה/לור"),
    ("MANTM.TTF",   "Guttman Mantova",      "סריף עתיק — ספר עתיק"),
    ("MANTDEC.TTF", "Guttman Mantova Decor","מעוטר — כותרות פנטזיה"),
    ("DROGM.TTF",   "Guttman Drogolin",     "עתיק / דקורטיבי"),
    ("GHAIM.TTF",   "Guttman Chaim",        "סריף רך ונעים"),
    ("STAM.TTF",    "STA\"M",               "כתב סופר ימי-ביניימי — הכי אטמוספרי"),
    ("RASHI.TTF",   "Rashi",                "כתב רש\"י — עתיק (סיכון קריאוּת)"),
    ("GYADL.TTF",   "Guttman Yad",          "כתב-יד קליגרפי"),
    ("ARAM.TTF",    "Aram",                 "ארמי / עתיק"),
    ("lvnm.ttf",    "Levenim MT",           "מודרני נקי (להשוואה)"),
]

# sample texts (LOGICAL Hebrew; get_display handles RTL for the preview)
TITLE = "הזאב הלבן · הציד הפראי"
MENU = "משחק חדש · המשך · אפשרויות · יציאה"
DIALOG = "רוצה להישאר איתך עוד קצת."
MIXED = "רמת קושי: 3 · חיים 100% · ג'ראלט מריוויה"

W, H = 1240, 1754                        # A4 @ ~150dpi portrait
BG = (20, 18, 15)                        # near-black (Witcher dark)
GOLD = (216, 183, 121)                   # Witcher subtitle gold
CREAM = (225, 216, 200)
DIM = (150, 140, 120)
MARGIN = 60
PER_PAGE = 4

UI = lambda sz: ImageFont.truetype(os.path.join(FDIR, "arialbd.ttf"), sz)
UIR = lambda sz: ImageFont.truetype(os.path.join(FDIR, "arial.ttf"), sz)

def R(s):
    return get_display(s)

def draw_rtl(dr, xy_right, text, font, fill):
    """draw RTL text ending at x=xy_right[0] (right edge)."""
    disp = R(text)
    w = dr.textlength(disp, font=font)
    dr.text((xy_right[0] - w, xy_right[1]), disp, font=font, fill=fill)

def font_block(dr, y, idx, file, name, note):
    right = W - MARGIN
    path = os.path.join(FDIR, file)
    try:
        f_title = ImageFont.truetype(path, 40)
        f_body = ImageFont.truetype(path, 30)
        f_small = ImageFont.truetype(path, 26)
    except Exception as e:
        dr.text((MARGIN, y), f"{name}: FAILED {e}", font=UIR(22), fill=(200, 80, 80))
        return y + 60
    # label: number + latin name (LTR left) + hebrew note (RTL right)
    dr.text((MARGIN, y), f"{idx}.  {name}", font=UI(26), fill=CREAM)
    draw_rtl(dr, (right, y + 2), note, UIR(22), DIM)
    y += 44
    dr.line((MARGIN, y, W - MARGIN, y), fill=(60, 54, 46), width=1)
    y += 16
    draw_rtl(dr, (right, y), TITLE, f_title, GOLD); y += 56
    draw_rtl(dr, (right, y), MENU, f_body, CREAM); y += 44
    draw_rtl(dr, (right, y), DIALOG, f_body, GOLD); y += 44
    draw_rtl(dr, (right, y), MIXED, f_small, CREAM); y += 52
    return y + 22

def main():
    pages = []
    # header page content merged into first page top
    i = 0
    while i < len(FONTS):
        img = Image.new("RGB", (W, H), BG)
        dr = ImageDraw.Draw(img)
        y = MARGIN
        if i == 0:
            dr.text((MARGIN, y), "The Witcher 3 — Hebrew Font Samples", font=UI(34), fill=GOLD)
            y += 44
            draw_rtl(dr, (W - MARGIN, y), "בחר את הפונט המתאים — הטקסט מוצג בזהב על רקע כהה כמו במשחק", UIR(22), DIM)
            y += 44
        for j in range(PER_PAGE):
            if i + j >= len(FONTS):
                break
            file, name, note = FONTS[i + j]
            y = font_block(dr, y, i + j + 1, file, name, note)
        # footer
        dr.text((MARGIN, H - 40), f"page {i//PER_PAGE + 1} / {(len(FONTS)+PER_PAGE-1)//PER_PAGE}",
                font=UIR(18), fill=(90, 84, 74))
        pages.append(img)
        i += PER_PAGE
    write_pdf(pages, OUT)
    print("wrote", OUT, "|", len(pages), "pages,", len(FONTS), "fonts")

if __name__ == "__main__":
    main()
