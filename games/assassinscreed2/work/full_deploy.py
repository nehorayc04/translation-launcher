"""AC2 FULL Hebrew deploy — clean: accented carriers (English/Italian stay Latin & readable).

Reuses the proven glyph rendering (fringe-erase + uniform ascent) but draws the 27 Hebrew
glyphs into 27 IN-GAME-VERIFIED accented cells (map c:/tmp/ac2_carriers27.json), then encodes
ALL 10,003 lines (ui:->English pkg, sub:->Subtitles pkg) via ac2_rtl.to_visual + carrier map.
Non-Hebrew (Latin landmark names, brands, tokens, digits) passes through unchanged -> renders
normally, no gibberish.  REVERT = copy _HE_BACKUP/*.forge back.
"""
import sys, os, json, shutil, subprocess
import numpy as np
from PIL import Image, ImageFont, ImageDraw
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work"
sys.path.insert(0, W); sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_forge, ac2_font, ac2_locwrite, ac2_loc, ac2_rtl

GAME = r"D:/Games/Assassin's Creed II"
OUT  = r"c:/tmp/ac2_full"; os.makedirs(OUT, exist_ok=True)
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
LIGHT = "AC2Aaux_ProLight_Latin_1_MapDesc"
FONT = "lvnm.ttf"
boxes = json.load(open("c:/tmp/boxes_light.json"))
cmap  = json.load(open("c:/tmp/ac2_carriers27.json", encoding="utf-8"))
H2C   = cmap["H2C"]                      # hebrew letter -> accented carrier char
CELL  = {c: cmap["CELL"][c] for c in cmap["CELL"]}   # carrier char -> box index
HEB   = list("אבגדהוזחטיכךלמםנןסעפףצץקרשת")
DESC  = "ךןקףץ"
STD   = [c for c in HEB if c not in "ל"+DESC]

# ---- metrics -------------------------------------------------------------------
REF = 400
rf  = ImageFont.truetype("C:/Windows/Fonts/"+FONT, REF)
_p  = ImageDraw.Draw(Image.new("L", (8, 8)))
met = {}
for c in HEB:
    b = _p.textbbox((0, 0), c, font=rf, anchor="ls")
    met[c] = dict(x0=b[0], asc=-b[1], w=b[2]-b[0], desc=max(0, b[3]))
std_asc  = float(np.median([met[c]["asc"] for c in STD]))
max_desc = max(met[c]["desc"] for c in DESC)
lam_r    = met["ל"]["asc"] / std_asc
desc_r   = max_desc / std_asc
DK = 0.62; SS = 4; RING = 3; EXPAND = 1.10

cw = {h: boxes[CELL[H2C[h]]][2]-boxes[CELL[H2C[h]]][0]+1 for h in HEB}
ch_h = {h: boxes[CELL[H2C[h]]][3]-boxes[CELL[H2C[h]]][1]+1 for h in HEB}
# uniform height budget = smallest usable cell (keeps every letter the SAME on-screen size)
H_CELL = min(ch_h.values()) - 1
s_v = H_CELL / (met["ל"]["asc"] + max_desc*DK)
s   = min(s_v, min(cw[h]/met[h]["w"] for h in HEB))
GA_STD = int(round(std_asc*s)); GA_LAM = int(round(GA_STD*lam_r)); GD = int(round(GA_STD*desc_r*DK))
baseline = H_CELL - GD
print(f"font={FONT}  uniform ascent={GA_STD}px  lamed={GA_LAM}px  tail={GD}px  cell budget={H_CELL}")

def glyph(chh, w, h):
    m = met[chh]; ga = GA_LAM if chh == "ל" else GA_STD; gd = GD if chh in DESC else 0
    gw = max(1, int(round(m["w"]*s))); gw = min(w, max(gw, min(int(round(gw*EXPAND)), w)))
    px = max(8, int(round(REF * (ga/(m["asc"]*s)) * s * SS)))
    f2 = ImageFont.truetype("C:/Windows/Fonts/"+FONT, px)
    b2 = _p.textbbox((0, 0), chh, font=f2, anchor="ls")
    a2, w2, x2, d2 = -b2[1], b2[2]-b2[0], b2[0], max(0, b2[3])
    big = Image.new("L", (px*3, px*3), 0)
    ImageDraw.Draw(big).text((px, px*2), chh, font=f2, fill=255, anchor="ls")
    arr = np.array(big); bot = px*2 + (min(d2, int(round(d2*DK))) if chh in DESC else 0)
    crop = arr[px*2-a2:bot, px+x2:px+x2+w2]
    g = Image.fromarray(crop).resize((gw, max(1, ga+gd)), Image.BOX)
    cell = Image.new("L", (w, h), 0); cell.paste(g, ((w-gw)//2, max(0, baseline-ga)))
    return np.array(cell)[::-1, :]

# ---- build the atlas ------------------------------------------------------------
fg, idx, at = ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge", LIGHT)
A = np.array(ac2_font.decode_image(at).convert("RGBA"))
inbox = np.zeros(A.shape[:2], bool)
for (x0, y0, x1, y1) in boxes: inbox[y0:y1+1, x0:x1+1] = True
# clear each carrier cell FULLY (wipes the original accented glyph incl. its diacritic blob)
for h in HEB:
    x0, y0, x1, y1 = boxes[CELL[H2C[h]]]
    A[y0:y1+1, x0:x1+1, :] = 0
# CLEAR the accent-mark blobs that sit ABOVE each accented carrier cell (parked follow-up #3).
# The accent glyph of À/É/… is a separate blob just above the base-letter cell; only accented
# chars (= our carriers) use it, so wiping it is safe for kept English. Clear (a) any small box
# above the carrier and (b) loose ink in a 22px band above it.
carrier_cells = {CELL[H2C[h]] for h in HEB}
acc_cleared = 0
for h in HEB:
    ci = CELL[H2C[h]]; x0, y0, x1, y1 = boxes[ci]; cwd = x1-x0+1
    # (a) accent BOXES above this carrier: ANY short box (<=20px tall = a diacritic, never an
    # English letter which is >=24px) whose bottom sits in the 30px band above the carrier and
    # x-overlaps it. Only accented chars use these -> safe for kept English.
    for j, (bx0, by0, bx1, by1) in enumerate(boxes):
        if j == ci or j in carrier_cells: continue
        xov = min(x1, bx1) - max(x0, bx0)
        if xov > 1 and y0-30 <= by1 <= y0+10 and (by1-by0+1) <= 20:
            acc_cleared += int((A[by0:by1+1, bx0:bx1+1, 3] > 0).sum())
            A[by0:by1+1, bx0:bx1+1, :] = 0
    # (b) loose ink (belongs to NO box = fringe/accent debris) in the 26px band above the carrier
    b0 = max(0, y0-26)
    band = A[b0:y0, x0:x1+1, 3]; bboxmask = inbox[b0:y0, x0:x1+1]
    loose = (band > 0) & ~bboxmask
    acc_cleared += int(loose.sum()); band[loose] = 0
print(f"accent blobs cleared above carriers: {acc_cleared} px")

# draw Hebrew
for h in HEB:
    x0, y0, x1, y1 = boxes[CELL[H2C[h]]]; w, hh = x1-x0+1, y1-y0+1
    al = glyph(h, w, hh)
    A[y0:y1+1, x0:x1+1, 3] = al
    sub = A[y0:y1+1, x0:x1+1, :3]; sub[al > 0] = 255
# erase the anti-alias fringe in a RING around each carrier cell (outside every glyph rect)
erased = 0
for h in HEB:
    x0, y0, x1, y1 = boxes[CELL[H2C[h]]]
    rx0, ry0, rx1, ry1 = max(0,x0-RING), max(0,y0-RING), min(A.shape[1]-1,x1+RING), min(A.shape[0]-1,y1+RING)
    ring = np.ones((ry1-ry0+1, rx1-rx0+1), bool); ring[y0-ry0:y1-ry0+1, x0-rx0:x1-rx0+1] = False
    sel = ring & ~inbox[ry0:ry1+1, rx0:rx1+1]
    a = A[ry0:ry1+1, rx0:rx1+1, 3]; erased += int((a[sel] > 0).sum()); a[sel] = 0
print(f"fringe erased around carrier cells: {erased} px")

png = OUT+"/atlas.png"; Image.fromarray(A, "RGBA").save(png)
subprocess.run([TEXCONV,"-nologo","-f","BC3_UNORM","-m","1","-y","-o",OUT.replace("/","\\"),png.replace("/","\\")],check=True,capture_output=True)
body = open(OUT+"/atlas.dds","rb").read()[128:128+at.texsize]
eo = OUT+"/DataPC_extra.forge"; shutil.copy(GAME+"/_HE_BACKUP/DataPC_extra.forge", eo)
ac2_forge.Forge.write_resource(eo, idx, at.rebuild(body)); shutil.copy(eo, GAME+"/DataPC_extra.forge")
print("atlas deployed")

# ---- encode all strings ---------------------------------------------------------
heb = json.load(open(r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/fleet/hebrew.json", encoding="utf-8"))
def enc(logical):
    vis = ac2_rtl.to_visual(logical)          # protects tokens, reverses Hebrew runs, keeps Latin
    return "".join(H2C.get(c, c) for c in vis) # map hebrew->carrier; Latin/digits/tokens pass through
ui  = {int(k.split(":",1)[1]): enc(v) for k, v in heb.items() if k.startswith("ui:")}
sub = {int(k.split(":",1)[1]): enc(v) for k, v in heb.items() if k.startswith("sub:")}
print(f"encoding UI {len(ui)} + SUB {len(sub)} = {len(ui)+len(sub)} lines")

shutil.copy(GAME+"/_HE_BACKUP/DataPC.forge", GAME+"/DataPC.forge")
for name, patch in (("LocalizationPackage_English", ui), ("LocalizationPackage_English_Subtitles", sub)):
    fgm = ac2_forge.Forge(GAME+"/_HE_BACKUP/DataPC.forge")
    li = fgm.by_name(name); slot,_,_ = fgm.full_slot(li)
    new = ac2_locwrite.rebuild(slot, patch)
    # roundtrip: a carrier char not in the rebuilt dict = black screen -> assert BEFORE deploy
    _,_,st = ac2_loc.decode_payload(ac2_loc.extract_payload(new)); d = {int(k):v for k,v in st}
    bad = [k for k,v in patch.items() if d.get(k) != v]
    assert not bad, f"{name} roundtrip fail: {bad[:5]}"
    ac2_forge.Forge.write_resource(GAME+"/DataPC.forge", li, new)
    print(f"  {name}: {len(patch)} strings written + roundtrip OK")
print("FULL DEPLOY DONE")
