"""Extract glyph boxes + shape-match the A-Z cells for ANY AC2 Latin font atlas.
Reusable for ProMedium / ProBold (ProLight already had boxes_light.json + latin_full_map.json)."""
import sys, json, os
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import ac2_forge, ac2_font
GAME = r"D:/Games/Assassin's Creed II"

def extract_boxes(A, minpix=18):
    mask = A > 60; H, Wd = mask.shape
    lab = np.zeros((H, Wd), np.int32); cur = 0; comps = []
    for y in range(H):
        for x in range(Wd):
            if mask[y, x] and lab[y, x] == 0:
                cur += 1; q = deque([(y, x)]); lab[y, x] = cur; pts = [(y, x)]
                while q:
                    cy, cx = q.popleft()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy+dy, cx+dx
                            if 0 <= ny < H and 0 <= nx < Wd and mask[ny, nx] and lab[ny, nx] == 0:
                                lab[ny, nx] = cur; q.append((ny, nx)); pts.append((ny, nx))
                if len(pts) >= minpix:
                    ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
                    comps.append([min(xs), min(ys), max(xs), max(ys)])
    # merge boxes that overlap in x AND are vertically close (accent+base -> one letter box)
    comps.sort(key=lambda b: (b[0], b[1]))
    return comps

def ref(ch):
    im = Image.new("L", (200, 200), 0); f = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 140)
    d = ImageDraw.Draw(im); bb = d.textbbox((0, 0), ch, font=f); d.text((-bb[0], -bb[1]), ch, font=f, fill=255)
    a = np.array(im) > 40; ys, xs = np.where(a); return a[ys.min():ys.max()+1, xs.min():xs.max()+1]

def iou(m1, m2):
    h = max(m1.shape[0], m2.shape[0]); w = max(m1.shape[1], m2.shape[1])
    a = np.array(Image.fromarray(m1.astype(np.uint8)*255).resize((w, h))) > 60
    b = np.array(Image.fromarray(m2.astype(np.uint8)*255).resize((w, h))) > 60
    u = (a | b).sum(); return (a & b).sum()/u if u else 0

def build(font_name, out_boxes, out_map):
    fg, idx, at = ac2_font.load(GAME+"/_HE_BACKUP/DataPC_extra.forge", font_name)
    A = np.array(ac2_font.decode_image(at).convert("RGBA"))[:, :, 3]
    boxes = extract_boxes(A)
    def cm(i):
        x0, y0, x1, y1 = boxes[i]; return A[y0:y1+1, x0:x1+1] > 60
    # match A-Z (only tall cells >=24px to avoid punctuation) greedily by IoU
    tall = [i for i, b in enumerate(boxes) if (b[3]-b[1]) >= 24 and (b[2]-b[0]) >= 8]
    amap = {}; taken = set()
    order = list("IJLTFHEKNMPRBDCUOQGSVWXYZA")  # distinctive shapes first
    for ch in order:
        r = ref(ch); best = None
        for i in tall:
            if i in taken: continue
            s = iou(r, cm(i))
            if best is None or s > best[1]: best = (i, s)
        if best and best[1] > 0.4: amap[ch] = {"blob": best[0], "box": boxes[best[0]], "iou": round(best[1], 2)}; taken.add(best[0])
    json.dump(boxes, open(out_boxes, "w"))
    json.dump(amap, open(out_map, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{font_name}: {len(boxes)} boxes, A-Z matched {len(amap)}/26  (>0.4 iou)")
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if ch in amap:
            b = amap[ch]["box"]; print(f"   {ch} cell {amap[ch]['blob']:3} {b[2]-b[0]+1}x{b[3]-b[1]+1} iou {amap[ch]['iou']}")
        else: print(f"   {ch} — NOT matched")
    return amap

if __name__ == "__main__":
    fam = sys.argv[1] if len(sys.argv) > 1 else "ProMedium"
    build(f"AC2Aaux_{fam}_Latin_1_MapDesc", f"c:/tmp/boxes_{fam}.json", f"c:/tmp/azmap_{fam}.json")
