import sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
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
live = np.array(ac2_font.decode_image(ac2_font.load(GAME+"/DataPC_extra.forge",
        "AC2Aaux_ProLight_Latin_1_MapDesc")[2]).convert("RGBA"))[..., 3]
inbox = np.zeros(live.shape, bool)
for (x0,y0,x1,y1) in boxes: inbox[y0:y1+1, x0:x1+1] = True
R = 3
tot_free = 0
print(f"ink in the {R}px ring around each Hebrew cell, split by whether it belongs to ANY blob bbox:")
for ch in sorted(H2L, key=lambda c: c):
    x0,y0,x1,y1 = boxes[LAT[H2L[ch]]]
    ry0,ry1 = max(0,y0-R), min(live.shape[0]-1, y1+R)
    rx0,rx1 = max(0,x0-R), min(live.shape[1]-1, x1+R)
    ring = np.ones((ry1-ry0+1, rx1-rx0+1), bool)
    ring[(y0-ry0):(y1-ry0+1), (x0-rx0):(x1-rx0+1)] = False
    sub = live[ry0:ry1+1, rx0:rx1+1]; own = inbox[ry0:ry1+1, rx0:rx1+1]
    free = ring & ~own & (sub > 8)          # fringe that belongs to NO glyph rect -> safe to erase
    used = ring &  own & (sub > 8)          # real neighbour glyph pixels -> must NOT touch
    tot_free += int(free.sum())
    if free.any() or used.any():
        print(f"  {ch} ({H2L[ch]}): erasable fringe {int(free.sum()):3} px (max {int(sub[free].max()) if free.any() else 0:3}) | "
              f"inside another glyph {int(used.sum()):3} px")
print("TOTAL erasable fringe:", tot_free, "px  <-- this is the bleed source")
