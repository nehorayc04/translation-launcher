import sys, os, json, shutil, subprocess
import numpy as np
from PIL import Image, ImageFont, ImageDraw
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work"
sys.path.insert(0, W); sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_forge, ac2_font

GAME = r"D:/Games/Assassin's Creed II"
OUT = r"c:/tmp/ac2_hex"; os.makedirs(OUT, exist_ok=True)
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
LIGHT = "AC2Aaux_ProLight_Latin_1_MapDesc"
boxes = json.load(open("c:/tmp/boxes_light.json"))
FNT = ImageFont.truetype(r"C:/Windows/Fonts/arialbd.ttf", 100)

def hex_glyph(i, w, h):
    txt = f"{i:02X}"
    im = Image.new("L", (300, 160), 0); d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), txt, font=FNT); d.text((-bb[0], -bb[1]), txt, font=FNT, fill=255)
    a = np.array(im); ys, xs = np.where(a > 40)
    a = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    g = Image.fromarray(a)
    sc = min(w/g.size[0], h/g.size[1])
    g = g.resize((max(1, int(g.size[0]*sc)), max(1, int(g.size[1]*sc))))
    cell = Image.new("L", (w, h), 0)
    cell.paste(g, ((w-g.size[0])//2, (h-g.size[1])//2))
    arr = np.array(cell)
    return arr[::-1, :]          # V-FLIP: atlas stores flipped, engine flips back

fg, idx, at = ac2_font.load(GAME + "/_HE_BACKUP/DataPC_extra.forge", LIGHT)
A = np.array(ac2_font.decode_image(at).convert("RGBA"))
for i, (x0, y0, x1, y1) in enumerate(boxes):
    w, h = x1-x0+1, y1-y0+1
    A[y0:y1+1, x0:x1+1, :3] = 255
    A[y0:y1+1, x0:x1+1, 3] = hex_glyph(i, w, h)
png = OUT + "/light_hex.png"; Image.fromarray(A, "RGBA").save(png)
subprocess.run([TEXCONV, "-nologo", "-f", "BC3_UNORM", "-m", "1", "-y", "-o", OUT.replace("/", "\\"), png.replace("/", "\\")], check=True, capture_output=True)
body = open(OUT + "/light_hex.dds", "rb").read()[128:128+at.texsize]
eo = OUT + "/DataPC_extra.forge"; shutil.copy(GAME + "/_HE_BACKUP/DataPC_extra.forge", eo)
ac2_forge.Forge.write_resource(eo, idx, at.rebuild(body))
shutil.copy(eo, GAME + "/DataPC_extra.forge")
print(f"deployed hex-index ProLight ({len(boxes)} blobs, V-flipped so it reads upright)")
