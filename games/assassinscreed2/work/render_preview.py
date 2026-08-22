"""Render exactly what the DEPLOYED atlas will draw in-game - no game launch needed."""
import sys, json
import numpy as np
from PIL import Image, ImageFont, ImageDraw, ImageFilter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work")
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_font

GAME = r"D:/Games/Assassin's Creed II"
boxes = json.load(open("c:/tmp/boxes_light.json"))
H2L = json.load(open("c:/tmp/ac2_v6/heb2lat.json"))
LAT = {"A":100,"B":26,"C":19,"D":41,"E":52,"F":143,"G":58,"H":80,"J":93,"K":103,
       "L":178,"M":120,"N":95,"O":82,"P":56,"Q":99,"R":25,"S":81,"T":61,"U":42,
       "V":98,"W":71,"X":20,"Y":57,"Z":40}
SC = 0.64                                     # measured atlas -> screen scale

# read the atlas that is DEPLOYED right now, plus the pristine one for the Latin reference
A_he = np.array(ac2_font.decode_image(ac2_font.load(GAME+"/DataPC_extra.forge",
        "AC2Aaux_ProLight_Latin_1_MapDesc")[2]).convert("RGBA"))[..., 3]
A_en = np.array(ac2_font.decode_image(ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge",
        "AC2Aaux_ProLight_Latin_1_MapDesc")[2]).convert("RGBA"))[..., 3]

def render(word, atlas, hebrew=True):
    cells = []
    for ch in reversed(word) if hebrew else word:
        if ch == " ":
            cells.append(np.zeros((42, 10), np.uint8)); continue
        blob = LAT[H2L[ch]] if hebrew else LAT[ch]
        x0, y0, x1, y1 = boxes[blob]
        cells.append(atlas[y0:y1+1, x0:x1+1][::-1, :])
    W = sum(g.shape[1]+4 for g in cells); Hh = max(g.shape[0] for g in cells)
    o = np.zeros((Hh, W), np.uint8); x = 0
    for g in cells:
        o[Hh-g.shape[0]:, x:x+g.shape[1]] = g; x += g.shape[1]+4
    im = Image.fromarray(o)
    return im.resize((max(1,int(W*SC)), max(1,int(Hh*SC))), Image.BOX)

W, Hh = 1180, 660
bg = Image.new("RGB", (W, Hh), (176, 173, 166))
d = ImageDraw.Draw(bg)
for i in range(0, W+300, 41): d.line([(i,0),(i-150,Hh)], fill=(189,187,181), width=2)
for j in range(0, Hh, 31):    d.line([(0,j),(W,j)],      fill=(184,182,176), width=1)
bg = bg.filter(ImageFilter.GaussianBlur(1.3))
d = ImageDraw.Draw(bg)
hb = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 19)
hn = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)

def put(im, x, y, col):
    bg.paste(Image.new("RGB", im.size, col), (x, y), im)

# --- 1) the menu exactly at in-game size -------------------------------------
d.text((W-30, 16), "1:1 — הגודל האמיתי במשחק"[::-1], font=hb, fill=(25,25,25), anchor="ra")
y = 52
for k, wd in enumerate(["מצב עלילה", "תוספות", "הגדרות", "יציאה"]):
    im = render(wd, A_he); x = W - 60 - im.size[0]
    if k == 0:
        bar = Image.new("RGB", (im.size[0]+36, im.size[1]+16), (149,20,24))
        bd = ImageDraw.Draw(bar)
        for t in range(0, bar.size[0], 6): bd.line([(t,0),(t-14,bar.size[1])], fill=(177,29,33), width=2)
        bg.paste(bar, (x-18, y-8)); put(im, x, y, (255,255,255))
        d.text((x-40, y+2), "← סרגל הבחירה של המשחק (הפסים)"[::-1], font=hn, fill=(120,25,25), anchor="ra")
    else:
        put(im, x, y, (66,63,58))
    y += im.size[1] + 20

# --- 2) x2 zoom + the game's own Latin for weight comparison -----------------
d.text((W-30, y+14), "×2 — השוואת משקל מול הפונט של המשחק"[::-1], font=hb, fill=(25,25,25), anchor="ra")
y += 46
en = render("STORY", A_en, hebrew=False)
en2 = en.resize((en.size[0]*2, en.size[1]*2), Image.LANCZOS)
put(en2, W-60-en2.size[0], y, (66,63,58))
d.text((W-70-en2.size[0], y+18), "STORY — המקורי", font=hn, fill=(40,40,40), anchor="ra")
y += en2.size[1] + 14
he = render("הגדרות תל", A_he)
he2 = he.resize((he.size[0]*2, he.size[1]*2), Image.LANCZOS)
put(he2, W-60-he2.size[0], y, (66,63,58))
d.text((W-70-he2.size[0], y+18), "העברית — ל' גבוהה מ-ת'"[::-1], font=hn, fill=(40,40,40), anchor="ra")
y += he2.size[1] + 26

# --- 3) the whole alphabet ---------------------------------------------------
d.text((W-30, y), "כל האותיות (×2)"[::-1], font=hb, fill=(25,25,25), anchor="ra")
y += 30
for row in ["אבגדהוזחטי", "כלמנסעפצקר", "שתךםן"]:
    im = render(row, A_he); im = im.resize((im.size[0]*2, im.size[1]*2), Image.LANCZOS)
    put(im, W-60-im.size[0], y, (66,63,58)); y += im.size[1]+10

bg.save("c:/tmp/final_look.png")
print("saved c:/tmp/final_look.png")
