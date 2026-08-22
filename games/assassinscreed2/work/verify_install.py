import sys, json
import numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/work")
sys.path.insert(0, r"c:/Users/Nehoray_Cohen/Projects/Game translator/games/assassinscreed2/tools")
import ac2_forge, ac2_font, ac2_loc

GAME = r"D:/Games/Assassin's Creed II"
boxes = json.load(open("c:/tmp/boxes_light.json"))
H2L = json.load(open("c:/tmp/ac2_v6/heb2lat.json"))
LAT = {"A":100,"B":26,"C":19,"D":41,"E":52,"F":143,"G":58,"H":80,"J":93,"K":103,
       "L":178,"M":120,"N":95,"O":82,"P":56,"Q":99,"R":25,"S":81,"T":61,"U":42,
       "V":98,"W":71,"X":20,"Y":57,"Z":40}
MENU = {284785:"מצב עלילה",284786:"תוספות",276696:"הגדרות",276965:"הגדרות",
        287822:"יציאה",286119:"המשך",286062:"המשך",276691:"יציאה"}

ok = True
# --- 1) the font atlas actually in the game ---------------------------------
live = np.array(ac2_font.decode_image(ac2_font.load(GAME+"/DataPC_extra.forge",
        "AC2Aaux_ProLight_Latin_1_MapDesc")[2]).convert("RGBA"))[..., 3]
van  = np.array(ac2_font.decode_image(ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge",
        "AC2Aaux_ProLight_Latin_1_MapDesc")[2]).convert("RGBA"))[..., 3]
changed = untouched = 0
for ch, lat in H2L.items():
    x0,y0,x1,y1 = boxes[LAT[lat]]
    a = live[y0:y1+1, x0:x1+1]; b = van[y0:y1+1, x0:x1+1]
    if a.max() == 0: print(f"  !! {ch} -> cell {lat} is EMPTY"); ok = False
    elif np.array_equal(a, b): untouched += 1; print(f"  !! {ch} -> cell {lat} still vanilla"); ok = False
    else: changed += 1
print(f"atlas: {changed}/{len(H2L)} Hebrew cells written, {untouched} untouched")
# nothing outside our cells may differ
mask = np.zeros_like(live, bool)
for lat in H2L.values():
    x0,y0,x1,y1 = boxes[LAT[lat]]; mask[y0:y1+1, x0:x1+1] = True
# texconv re-compresses the WHOLE atlas, so every BC3 block shifts a little; and we
# DELIBERATELY erase the anti-aliased fringe in a 3px ring around each Hebrew cell
# (those pixels lie outside EVERY glyph rect, so nothing can be reading them).
# What must never happen is real glyph ink being destroyed.
RING = 3
inbox = np.zeros(live.shape, bool)
for (bx0, by0, bx1, by1) in boxes: inbox[by0:by1+1, bx0:bx1+1] = True
ringmask = np.zeros(live.shape, bool)
for lat in H2L.values():
    x0, y0, x1, y1 = boxes[LAT[lat]]
    ringmask[max(0,y0-RING):y1+1+RING, max(0,x0-RING):x1+1+RING] = True
ringmask &= ~mask & ~inbox                      # the fringe we intentionally cleared
outside = (live != van) & ~mask & ~ringmask
delta = np.abs(live.astype(int) - van.astype(int))[outside]
lost = int(((van > 128) & (live < 64) & ~mask & ~ringmask).sum())
print(f"atlas: fringe deliberately erased in the {RING}px ring = {int(ringmask.sum())} px slots")
print(f"atlas: elsewhere outside our cells -> {int(outside.sum())} px re-compressed "
      f"(max delta {int(delta.max()) if delta.size else 0}/255), glyph ink destroyed = {lost} px")
ok &= lost == 0 and (delta.max() if delta.size else 0) <= 48

# --- 2) the localization actually in the game -------------------------------
fg = ac2_forge.Forge(GAME+"/DataPC.forge")
li = fg.by_name("LocalizationPackage_English"); slot,_,_ = fg.full_slot(li)
_s,_p,strings = ac2_loc.decode_payload(ac2_loc.extract_payload(slot))
d = dict(strings)
def vis(w): return "".join(" " if c==" " else H2L[c] for c in reversed(w))
for sid, heb in MENU.items():
    got = d.get(sid)
    good = got == vis(heb)
    ok &= good
    print(f"  {sid}: {heb!r} -> {got!r} {'OK' if good else '<-- MISMATCH'}")
print(f"loc: {len(strings)} strings intact")
print("\nRESULT:", "INSTALL VERIFIED OK" if ok else "PROBLEM FOUND")
