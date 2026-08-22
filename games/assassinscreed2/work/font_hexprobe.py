"""Deploy a hex-index atlas for ProMedium+ProBold + set a control-name string to the 26 A-Z
carriers, so the Controls screen shows each carrier's real cell index (MEASURED, not guessed)."""
import sys, os, json, shutil, subprocess
import numpy as np
from PIL import Image, ImageFont, ImageDraw
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, W); sys.path.insert(0, os.path.join(W, "..", "tools"))
import ac2_forge, ac2_font, ac2_locwrite, ac2_loc
from font_map import extract_boxes
GAME = r"D:/Games/Assassin's Creed II"
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
OUT = "c:/tmp/ac2_fonthex"; os.makedirs(OUT, exist_ok=True)
FNT = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 100)

def hex_glyph(i, w, h):
    im = Image.new("L", (300, 160), 0); d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), f"{i:02X}", font=FNT); d.text((-bb[0], -bb[1]), f"{i:02X}", font=FNT, fill=255)
    a = np.array(im); ys, xs = np.where(a > 40); a = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    g = Image.fromarray(a); sc = min(w/g.size[0], h/g.size[1])
    g = g.resize((max(1, int(g.size[0]*sc)), max(1, int(g.size[1]*sc))))
    cell = Image.new("L", (w, h), 0); cell.paste(g, ((w-g.size[0])//2, (h-g.size[1])//2))
    return np.array(cell)[::-1, :]

for fam in ("ProMedium", "ProBold"):
    fg, idx, at = ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge", f"AC2Aaux_{fam}_Latin_1_MapDesc")
    A = np.array(ac2_font.decode_image(at).convert("RGBA"))
    boxes = extract_boxes(A[:, :, 3]); json.dump(boxes, open(f"c:/tmp/boxes_{fam}.json", "w"))
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        A[y0:y1+1, x0:x1+1, :3] = 255; A[y0:y1+1, x0:x1+1, 3] = hex_glyph(i, x1-x0+1, y1-y0+1)
    png = OUT+f"/{fam}.png"; Image.fromarray(A, "RGBA").save(png)
    subprocess.run([TEXCONV, "-nologo", "-f", "BC3_UNORM", "-m", "1", "-y", "-o", OUT.replace("/", "\\"), png.replace("/", "\\")], check=True, capture_output=True)
    body = open(OUT+f"/{fam}.dds", "rb").read()[128:128+at.texsize]
    ac2_forge.Forge.write_resource(GAME+"/DataPC_extra.forge", idx, at.rebuild(body))
    print(f"{fam}: hex atlas deployed ({len(boxes)} boxes)")

# set control-name strings to known carrier sequences (Latin, so ProMedium/ProBold renders them)
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
patch = {287736: ALPHA, 287737: ALPHA[13:], 287739: "ABCDEFGHIJKLM"}   # Move Forward / etc.
fg = ac2_forge.Forge(GAME+"/_HE_BACKUP/DataPC.forge"); li = fg.by_name("LocalizationPackage_English"); slot, _, _ = fg.full_slot(li)
# preserve the rest of the current live loc: read live, patch only these
live = ac2_forge.Forge(GAME+"/DataPC.forge"); lslot, _, _ = live.full_slot(live.by_name("LocalizationPackage_English"))
_, _, st = ac2_loc.decode_payload(ac2_loc.extract_payload(lslot)); cur = {int(k): v for k, v in st}
cur.update(patch)
new = ac2_locwrite.rebuild(slot, cur)
ac2_forge.Forge.write_resource(GAME+"/DataPC.forge", li, new)
print("probe strings set: 287736=A..Z (Move Forward line). Navigate to Options -> Controls.")
