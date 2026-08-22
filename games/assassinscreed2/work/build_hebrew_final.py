"""AC2 Hebrew - final build.
Fixes over v6:
  1. erase the anti-aliased fringe in a 3px ring around every Hebrew cell
     (it belongs to NO glyph rect, so this is safe) -> kills the faint marks
     the engine was dragging in from neighbouring atlas glyphs.
  2. force EVERY standard letter to the exact same pixel ascent -> no more
     'ו / ג / ק look shorter than the rest'.
  3. rasterise at 4x the target instead of 10x -> straight, un-warped strokes.
"""
import sys, os, json, shutil, subprocess
import numpy as np
from PIL import Image, ImageFont, ImageDraw
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work"
sys.path.insert(0, W); sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_forge, ac2_font, ac2_locwrite, ac2_loc

PREVIEW = "--preview" in sys.argv
FONT = sys.argv[sys.argv.index("--font")+1] if "--font" in sys.argv else "lvnm.ttf"
GAME = r"D:/Games/Assassin's Creed II"
OUT  = r"c:/tmp/ac2_v8"; os.makedirs(OUT, exist_ok=True)
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
LIGHT = "AC2Aaux_ProLight_Latin_1_MapDesc"
boxes = json.load(open("c:/tmp/boxes_light.json"))
CELL = {"A":100,"B":26,"C":19,"D":41,"E":52,"F":143,"G":58,"H":80,"J":93,"K":103,
        "L":178,"M":120,"N":95,"O":82,"P":56,"Q":99,"R":25,"S":81,"T":61,"U":42,
        "V":98,"W":71,"X":20,"Y":57,"Z":40}
HEB = list("אבגדהוזחטיכלמנסעפצקרשתךםן")
DESC = "ךןקףץ"
STD  = [c for c in HEB if c not in "ל"+DESC]
DK   = 0.62
H_CELL = 42
EXPAND = 1.10
SS = 4                      # supersample factor (was ~10 -> caused warped diagonals)
RING = 3                    # fringe ring to erase around each cell

# ---- metrics at a reference size -------------------------------------------
REF = 400
rf  = ImageFont.truetype("C:/Windows/Fonts/"+FONT, REF)
_p  = ImageDraw.Draw(Image.new("L", (8, 8)))
met = {}
for c in HEB:
    b = _p.textbbox((0, 0), c, font=rf, anchor="ls")
    met[c] = dict(x0=b[0], asc=-b[1], w=b[2]-b[0], desc=max(0, b[3]))
std_asc = float(np.median([met[c]["asc"] for c in STD]))
max_desc = max(met[c]["desc"] for c in DESC if c in met)
lam_r  = met["ל"]["asc"] / std_asc
desc_r = max_desc / std_asc

cw = {l: boxes[CELL[l]][2]-boxes[CELL[l]][0]+1 for l in CELL}
_rank = {h: l for h, l in zip(sorted(HEB, key=lambda c: met[c]["w"]), sorted(CELL, key=lambda l: cw[l]))}
s_v = H_CELL / (met["ל"]["asc"] + max_desc*DK)
s   = min(s_v, min(cw[_rank[c]]/met[c]["w"] for c in HEB))
free = sorted(CELL, key=lambda l: cw[l]); H2L = {}
for ch in sorted(HEB, key=lambda c: -met[c]["w"]):
    need = met[ch]["w"]*s
    pick = next((l for l in free if cw[l]+0.5 >= need), free[-1]); H2L[ch] = pick; free.remove(pick)

GA_STD = int(round(std_asc*s))                      # ONE ascent for every standard letter
GA_LAM = int(round(GA_STD*lam_r))
GD     = int(round(GA_STD*desc_r*DK))
baseline = H_CELL - GD
print(f"font={FONT}  standard ascent={GA_STD}px (identical for all)  lamed={GA_LAM}px  "
      f"tail={GD}px  baseline@{baseline}/{H_CELL}")

def glyph(ch, w, h):
    m = met[ch]
    ga = GA_LAM if ch == "ל" else GA_STD
    gd = GD if ch in DESC else 0
    gw = max(1, int(round(m["w"]*s)))
    gw = min(w, max(gw, min(int(round(gw*EXPAND)), w)))
    # rasterise at SSx the final size, then box-average down
    px = max(8, int(round(REF * (ga/ (m["asc"]*s)) * s * SS)))   # font px so that asc ~= ga*SS
    f2 = ImageFont.truetype("C:/Windows/Fonts/"+FONT, px)
    b2 = _p.textbbox((0, 0), ch, font=f2, anchor="ls")
    a2, w2, x2, d2 = -b2[1], b2[2]-b2[0], b2[0], max(0, b2[3])
    big = Image.new("L", (px*3, px*3), 0)
    ImageDraw.Draw(big).text((px, px*2), ch, font=f2, fill=255, anchor="ls")
    arr = np.array(big)
    bot = px*2 + (min(d2, int(round(d2*DK))) if ch in DESC else 0)
    crop = arr[px*2-a2:bot, px+x2:px+x2+w2]
    g = Image.fromarray(crop).resize((gw, max(1, ga+gd)), Image.BOX)
    cell = Image.new("L", (w, h), 0)
    cell.paste(g, ((w-gw)//2, max(0, baseline-ga)))
    return np.array(cell)[::-1, :]

fg, idx, at = ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge", LIGHT)
A = np.array(ac2_font.decode_image(at).convert("RGBA"))
ORIG = A.copy()

# --- fix 1: erase the bleed-causing fringe (only pixels outside EVERY glyph rect)
inbox = np.zeros(A.shape[:2], bool)
for (x0, y0, x1, y1) in boxes: inbox[y0:y1+1, x0:x1+1] = True
erased = 0
for lat in H2L.values():
    x0, y0, x1, y1 = boxes[CELL[lat]]
    ry0, ry1 = max(0, y0-RING), min(A.shape[0]-1, y1+RING)
    rx0, rx1 = max(0, x0-RING), min(A.shape[1]-1, x1+RING)
    ring = np.ones((ry1-ry0+1, rx1-rx0+1), bool)
    ring[(y0-ry0):(y1-ry0+1), (x0-rx0):(x1-rx0+1)] = False
    sel = ring & ~inbox[ry0:ry1+1, rx0:rx1+1]
    sub = A[ry0:ry1+1, rx0:rx1+1, 3]
    erased += int((sub[sel] > 0).sum()); sub[sel] = 0
print(f"fringe erased around cells: {erased} px (0 of them belonged to any glyph)")

for ch in HEB:
    x0, y0, x1, y1 = boxes[CELL[H2L[ch]]]
    al = glyph(ch, x1-x0+1, y1-y0+1)
    A[y0:y1+1, x0:x1+1, 3] = al
    sub = A[y0:y1+1, x0:x1+1, :3]; sub[al > 0] = 255

def strip(word, arr, m=None):
    cs = []
    for c in reversed(word):
        if c == " ": cs.append(np.zeros((H_CELL, 9), np.uint8)); continue
        x0, y0, x1, y1 = boxes[CELL[m[c] if m else c]]
        cs.append(arr[y0:y1+1, x0:x1+1, 3][::-1, :])
    Wd = sum(g.shape[1]+4 for g in cs); Hh = max(g.shape[0] for g in cs)
    o = np.zeros((Hh, Wd), np.uint8); x = 0
    for g in cs: o[Hh-g.shape[0]:, x:x+g.shape[1]] = g; x += g.shape[1]+4
    im = Image.fromarray(o)
    return im.resize((max(1, int(Wd*0.64)), max(1, int(Hh*0.64))), Image.BOX)

if PREVIEW:
    rows = [("STORY (game)", strip("YROTS", ORIG, {c: c for c in "YROTS"}))]
    for wd in ["מצב עלילה", "תוספות", "הגדרות", "יציאה", "אבגדהוזחטי", "כלמנסעפצקר", "שתךםן"]:
        rows.append((wd, strip(wd, A, H2L)))
    Z = 4; Wm = max(r[1].size[0] for r in rows)
    canv = Image.new("RGB", (Wm*Z+430, sum(r[1].size[1]*Z+18 for r in rows)+14), (150, 146, 140))
    dr = ImageDraw.Draw(canv); lab = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20); y = 6
    for name, im in rows:
        z = im.resize((im.size[0]*Z, im.size[1]*Z), Image.NEAREST)
        canv.paste(Image.new("RGB", z.size, (58, 56, 53)), (420, y), z)
        dr.text((6, y+8), name, font=lab, fill=(15, 15, 15)); y += z.size[1]+18
    canv.save("c:/tmp/preview_v8.png"); print("preview -> c:/tmp/preview_v8.png"); sys.exit(0)

png = OUT+"/he.png"; Image.fromarray(A, "RGBA").save(png)
subprocess.run([TEXCONV, "-nologo", "-f", "BC3_UNORM", "-m", "1", "-y", "-o", OUT.replace("/", "\\"), png.replace("/", "\\")], check=True, capture_output=True)
body = open(OUT+"/he.dds", "rb").read()[128:128+at.texsize]
eo = OUT+"/DataPC_extra.forge"; shutil.copy(GAME+"/_HE_BACKUP/DataPC_extra.forge", eo)
ac2_forge.Forge.write_resource(eo, idx, at.rebuild(body)); shutil.copy(eo, GAME+"/DataPC_extra.forge")
def vis(w): return "".join(" " if c == " " else H2L[c] for c in reversed(w))
MENU = {284785:"מצב עלילה", 284786:"תוספות", 276696:"הגדרות", 276965:"הגדרות",
        287822:"יציאה", 286119:"המשך", 286062:"המשך", 276691:"יציאה"}
fgm = ac2_forge.Forge(GAME+"/_HE_BACKUP/DataPC.forge")
li = fgm.by_name("LocalizationPackage_English"); slot,_,_ = fgm.full_slot(li)
new_loc = ac2_locwrite.rebuild(slot, {k: vis(v) for k, v in MENU.items()})
_s,_p2,_str = ac2_loc.decode_payload(ac2_loc.extract_payload(new_loc)); _d = dict(_str)
for k, v in MENU.items(): assert _d[k] == vis(v), f"roundtrip fail {k}"
shutil.copy(GAME+"/_HE_BACKUP/DataPC.forge", GAME+"/DataPC.forge")
ac2_forge.Forge.write_resource(GAME+"/DataPC.forge", li, new_loc)
json.dump(H2L, open(OUT+"/heb2lat.json", "w"), ensure_ascii=False)
json.dump(H2L, open("c:/tmp/ac2_v6/heb2lat.json", "w"), ensure_ascii=False)
print("deployed + roundtrip verified")
