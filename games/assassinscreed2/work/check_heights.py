import sys, json, subprocess
import numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work")
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
# build the atlas in-memory by importing the builder's preview path is awkward; just read the deployed one
import ac2_font
GAME = r"D:/Games/Assassin's Creed II"
boxes = json.load(open("c:/tmp/boxes_light.json"))
H2L = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "c:/tmp/ac2_v8/heb2lat.json"))
LAT = {"A":100,"B":26,"C":19,"D":41,"E":52,"F":143,"G":58,"H":80,"J":93,"K":103,
       "L":178,"M":120,"N":95,"O":82,"P":56,"Q":99,"R":25,"S":81,"T":61,"U":42,
       "V":98,"W":71,"X":20,"Y":57,"Z":40}
A = np.array(ac2_font.decode_image(ac2_font.load(GAME+"/DataPC_extra.forge",
      "AC2Aaux_ProLight_Latin_1_MapDesc")[2]).convert("RGBA"))[..., 3]
print(f"{'ל':>2} {'cell':>4} {'top':>4} {'bottom':>6} {'height':>6}   (rows measured from the CELL TOP, upright)")
tops, bots = {}, {}
for ch in "אבגדהוזחטיכלמנסעפצקרשתךםן":
    x0,y0,x1,y1 = boxes[LAT[H2L[ch]]]
    g = A[y0:y1+1, x0:x1+1][::-1, :]          # upright
    ys = np.where((g > 40).any(axis=1))[0]
    if not len(ys): print(f" {ch}  EMPTY"); continue
    tops[ch], bots[ch] = int(ys.min()), int(ys.max())
    print(f" {ch} {H2L[ch]:>4} {ys.min():4} {ys.max():6} {ys.max()-ys.min()+1:6}")
std = [c for c in tops if c not in "לךןקי"]
print("\nSTANDARD letters (excluding ל, finals, ק, י):")
print("  top    rows :", sorted(set(tops[c] for c in std)))
print("  bottom rows :", sorted(set(bots[c] for c in std)))
print("  -> heights  :", sorted(set(bots[c]-tops[c]+1 for c in std)))
print(f"\n  ל  top {tops.get('ל')} (should be ABOVE the standard top)")
for c in "ךןק":
    if c in bots: print(f"  {c}  bottom {bots[c]} (should be BELOW the standard bottom)")
print(f"  י  top {tops.get('י')} (yod floats high - its INK is short, that is correct)")
