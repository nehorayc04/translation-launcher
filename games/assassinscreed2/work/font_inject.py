"""Inject the SAME Hebrew glyphs into another AC2 Latin font (ProMedium / ProBold), using that
font's A-Z cell map (azmap_<fam>.json). Reuses ProLight's proven glyph rendering (fringe-erase +
uniform ascent). Carrier->Hebrew is identical across fonts so a stored string renders the same
Hebrew everywhere. Deploys the modified atlas into the live DataPC_extra.forge."""
import sys, os, json, shutil, subprocess
import numpy as np
from PIL import Image, ImageFont, ImageDraw, ImageFilter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W); sys.path.insert(0, os.path.join(W, "..", "tools"))
import ac2_forge, ac2_font
GAME = r"D:/Games/Assassin's Creed II"
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
FONT = os.environ.get("AC2_FONT", "lvnm.ttf")     # the PROVEN ProLight font: thin geometric strokes, aspect ~0.88
OUT = "c:/tmp/ac2_fontinj"; os.makedirs(OUT, exist_ok=True)

fam = sys.argv[1]                                    # ProMedium | ProBold
FRES = f"AC2Aaux_{fam}_Latin_1_MapDesc"
boxes = json.load(open(f"c:/tmp/boxes_{fam}.json"))
azmap = json.load(open(f"c:/tmp/azmap_{fam}.json", encoding="utf-8"))
H2L = json.load(open("c:/tmp/ac2_v8/heb2lat.json", encoding="utf-8")); H2L["ף"] = H2L["פ"]; H2L["ץ"] = H2L["צ"]
CELL = {c: azmap[c]["blob"] for c in azmap}          # carrier letter -> this font's box index
# carrier -> hebrew (inverse of H2L; finals share their base's carrier so pick a base letter)
C2H = {}
for h, c in H2L.items():
    if h in "ףץ": continue                           # finals render as base (same carrier)
    C2H[c] = h
HEB = list(C2H.values()); DESC = "ךןקףץ"; STD = [c for c in HEB if c not in "ל"+DESC]

REF = 400; rf = ImageFont.truetype("C:/Windows/Fonts/"+FONT, REF); _p = ImageDraw.Draw(Image.new("L", (8, 8)))
met = {}
for c in HEB:
    b = _p.textbbox((0, 0), c, font=rf, anchor="ls"); met[c] = dict(x0=b[0], asc=-b[1], w=b[2]-b[0], desc=max(0, b[3]))
std_asc = float(np.median([met[c]["asc"] for c in STD])); max_desc = max(met[c]["desc"] for c in DESC if c in met)
lam_r = met["ל"]["asc"]/std_asc; desc_r = max_desc/std_asc
DK = 0.62; SS = 6; RING = 3; EXPAND = 1.10        # SS=6: sharper supersample for small ProMedium cells
WIDEN = float(os.environ.get("AC2_WIDEN", "1.08"))   # near-natural width; over-widening clipped edge strokes (#1)
INSET = int(os.environ.get("AC2_INSET", "2"))        # keep strokes off the cell edge so the game's UV can't clip them
BOLD  = int(os.environ.get("AC2_BOLD", "0"))          # 0 = keep antialiasing; a binary/dilated glyph LOST its gap on downscale (#1)
carriers = [c for c in CELL if c in C2H]
cw = {c: boxes[CELL[c]][2]-boxes[CELL[c]][0]+1 for c in carriers}
chh = {c: boxes[CELL[c]][3]-boxes[CELL[c]][1]+1 for c in carriers}
# ONE uniform ascent that fits EVERY carrier cell (incl. the short ה/ת cells) -> every letter
# renders at the SAME on-screen height, so ה/ת no longer stand out / look flattened, and NOTHING
# is ever scaled-down/warped (the scale-down was what made ה/ת look "flipped/short").
def _bound(c):                               # max ascent this carrier's glyph can take in its cell
    h = chh[c] - 1; ch = C2H[c]
    if ch == "ל":  return h/lam_r
    if ch in DESC: return h/(1.0 + desc_r*DK)
    return float(h)
GA_STD = int(min(_bound(c) for c in carriers))   # binding constraint = the shortest cell
GA_LAM = int(round(GA_STD*lam_r)); GD = int(round(GA_STD*desc_r*DK))
s_eff  = GA_STD/std_asc
print(f"{fam}: uniform ascent={GA_STD}px  lamed={GA_LAM}  tail={GD}  carriers={len(carriers)}  (min cell {min(chh.values())})")

def glyph(ch, w, h):
    m = met[ch]
    ga = GA_LAM if ch == "ל" else GA_STD; gd = GD if ch in DESC else 0
    # Keep the glyph OFF the cell edges (INSET) so the game's UV sampling can't clip an edge stroke
    # (that clipping turned ה's thin right leg into a "box"), while still filling the cell for tight spacing.
    avail = max(6, w - 1 - 2*INSET)
    gw = max(6, min(avail, int(round(m["w"]*s_eff*WIDEN))))
    px = max(10, int(round(REF*(ga/m["asc"])*SS)))
    f2 = ImageFont.truetype("C:/Windows/Fonts/"+FONT, px); b2 = _p.textbbox((0, 0), ch, font=f2, anchor="ls")
    a2, w2, x2, d2 = -b2[1], b2[2]-b2[0], b2[0], max(0, b2[3])
    big = Image.new("L", (px*3, px*3), 0); ImageDraw.Draw(big).text((px, px*2), ch, font=f2, fill=255, anchor="ls")
    arr = np.array(big); bot = px*2 + (min(d2, int(round(d2*DK))) if ch in DESC else 0)
    crop = arr[px*2-a2:max(px*2-a2+1, bot), px+x2:px+x2+w2]
    # LANCZOS keeps thin strokes; a crisp threshold preserves the ה/ת gap that BOX-average smeared into a box (#1)
    gi = Image.fromarray(crop).resize((gw, max(1, ga+gd)), Image.LANCZOS)   # antialiased: the soft gap survives the game's 0.64 downscale
    for _ in range(BOLD):                    # (off by default) optional dilation if a stroke ever thins out in-game
        gi = gi.filter(ImageFilter.MaxFilter(3))
    g = np.array(gi, np.uint8)               # display orientation: row 0 = top bar
    if ch == "ה":                            # the game's filtering closes ה's small top-left gap -> looks like a box.
        gh, gwid = g.shape                   # DETACH only the TOP ~34% of the LEFT leg -> a clear gap, leg stays full-length.
        tb = max(2, gh // 8)                 # preserve the top bar
        g[tb:int(gh*0.34), :int(gwid*0.42)] = 0
    cell = np.zeros((h, w), np.uint8)
    base = h - 1 - gd                        # bottom-align to the cell (RTL letters sit on the baseline)
    yy = max(0, base-ga); xx = max(INSET, (w-gw)//2)
    gh, gw2 = g.shape
    cell[yy:yy+min(gh, h-yy), xx:xx+min(gw2, w-xx)] = g[:h-yy, :w-xx]
    return cell[::-1, :]

fg, idx, at = ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge", FRES)
A = np.array(ac2_font.decode_image(at).convert("RGBA"))
inbox = np.zeros(A.shape[:2], bool)
for (x0, y0, x1, y1) in boxes: inbox[y0:y1+1, x0:x1+1] = True
for c in carriers:
    x0, y0, x1, y1 = boxes[CELL[c]]; A[y0:y1+1, x0:x1+1, :] = 0
    al = glyph(C2H[c], x1-x0+1, y1-y0+1)
    A[y0:y1+1, x0:x1+1, 3] = al; sub = A[y0:y1+1, x0:x1+1, :3]; sub[al > 0] = 255
erased = 0
for c in carriers:
    x0, y0, x1, y1 = boxes[CELL[c]]
    rx0, ry0, rx1, ry1 = max(0, x0-RING), max(0, y0-RING), min(A.shape[1]-1, x1+RING), min(A.shape[0]-1, y1+RING)
    ring = np.ones((ry1-ry0+1, rx1-rx0+1), bool); ring[y0-ry0:y1-ry0+1, x0-rx0:x1-rx0+1] = False
    sel = ring & ~inbox[ry0:ry1+1, rx0:rx1+1]; a = A[ry0:ry1+1, rx0:rx1+1, 3]; erased += int((a[sel] > 0).sum()); a[sel] = 0
print(f"  fringe erased {erased}px")
if os.environ.get("AC2_PREVIEW"):            # offline: compose real words from THIS atlas + simulate the game's 0.64 downscale, then exit (no deploy)
    import ac2_rtl
    def _compose(text):
        cells = []
        for c in ac2_rtl.to_visual(text):
            if c == " ": cells.append(np.zeros((23, 9), np.uint8)); continue
            car = H2L.get(c)
            if not car or car not in azmap: cells.append(np.zeros((23, 9), np.uint8)); continue
            x0, y0, x1, y1 = boxes[azmap[car]["blob"]]
            g = A[y0:y1+1, x0:x1+1, 3][::-1, :]          # display orientation
            gg = np.zeros((23, g.shape[1]), np.uint8); gg[:min(23, g.shape[0])] = g[:23]
            cells.append(gg)
        return np.hstack(cells) if cells else np.zeros((23, 9), np.uint8)
    for w in ["לנוע קדימה", "זוז שמאלה", "יציאה ל-windows"]:
        s = _compose(w); H, Wd = s.shape
        ow, oh = max(1, int(round(Wd*0.64))), max(1, int(round(H*0.64)))
        Image.fromarray(s).resize((ow, oh), Image.BILINEAR).resize((ow*13, oh*13), Image.NEAREST).save(f"c:/tmp/sim/deploy_{fam}_{w[:6]}.png")
    print("  PREVIEW saved -> c:/tmp/sim/deploy_* (NOT deployed)"); sys.exit(0)
png = OUT+f"/{fam}.png"; Image.fromarray(A, "RGBA").save(png)
subprocess.run([TEXCONV, "-nologo", "-f", "BC3_UNORM", "-m", "1", "-y", "-o", OUT.replace("/", "\\"), png.replace("/", "\\")], check=True, capture_output=True)
body = open(OUT+f"/{fam}.dds", "rb").read()[128:128+at.texsize]
ac2_forge.Forge.write_resource(GAME+"/DataPC_extra.forge", idx, at.rebuild(body))
print(f"  {fam} Hebrew injected + deployed")
