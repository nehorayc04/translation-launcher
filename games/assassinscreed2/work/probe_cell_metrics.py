import sys, os, json, shutil, subprocess
import numpy as np
from PIL import Image
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work"
sys.path.insert(0, W); sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_forge, ac2_font, ac2_locwrite

GAME = r"D:/Games/Assassin's Creed II"
OUT = r"c:/tmp/ac2_probe"; os.makedirs(OUT, exist_ok=True)
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
LIGHT = "AC2Aaux_ProLight_Latin_1_MapDesc"
boxes = json.load(open("c:/tmp/boxes_light.json"))
CELL = {"A":100,"B":26,"C":19,"D":41,"E":52,"F":143,"G":58,"H":80,"J":93,"K":103,
        "L":178,"M":120,"N":95,"O":82,"P":56,"Q":99,"R":25,"S":81,"T":61,"U":42,
        "V":98,"W":71,"X":20,"Y":57,"Z":40}

fg, idx, at = ac2_font.load(GAME + "/_HE_BACKUP/DataPC_extra.forge", LIGHT)
A = np.array(ac2_font.decode_image(at).convert("RGBA"))
for lat, bi in CELL.items():
    x0, y0, x1, y1 = boxes[bi]
    A[y0:y1+1, x0:x1+1, :3] = 255
    A[y0:y1+1, x0:x1+1, 3]  = 255          # SOLID block over the exact bbox
png = OUT + "/solid.png"; Image.fromarray(A, "RGBA").save(png)
subprocess.run([TEXCONV,"-nologo","-f","BC3_UNORM","-m","1","-y","-o",OUT.replace("/","\\"),png.replace("/","\\")],check=True,capture_output=True)
body = open(OUT + "/solid.dds","rb").read()[128:128+at.texsize]
eo = OUT + "/DataPC_extra.forge"; shutil.copy(GAME + "/_HE_BACKUP/DataPC_extra.forge", eo)
ac2_forge.Forge.write_resource(eo, idx, at.rebuild(body))
shutil.copy(eo, GAME + "/DataPC_extra.forge")

MENU = {284785:"ABCDEFGH", 284786:"JKLMNOP", 276696:"QRSTUVW", 287822:"XYZ"}
fgm = ac2_forge.Forge(GAME + "/_HE_BACKUP/DataPC.forge")
li = fgm.by_name("LocalizationPackage_English"); slot,_,_ = fgm.full_slot(li)
new_loc = ac2_locwrite.rebuild(slot, MENU)
shutil.copy(GAME + "/_HE_BACKUP/DataPC.forge", GAME + "/DataPC.forge")
ac2_forge.Forge.write_resource(GAME + "/DataPC.forge", li, new_loc)
print("SOLID-BLOCK probe deployed:", {k:v for k,v in MENU.items()})
for lat in "ABCDEFGHJKLMNOPQRSTUVWXYZ":
    x0,y0,x1,y1 = boxes[CELL[lat]]
    print(f"  {lat}: blob {CELL[lat]:4} bbox w={x1-x0+1:3} h={y1-y0+1:3}")
