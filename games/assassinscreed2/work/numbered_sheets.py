import sys, json
import numpy as np
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from collections import deque

def blobs(alpha):
    A = np.array(alpha) > 64; H, Wd = A.shape
    lab = np.zeros((H, Wd), np.int32); cur = 0
    for y in range(H):
        for x in range(Wd):
            if A[y, x] and lab[y, x] == 0:
                cur += 1; q = deque([(y, x)]); lab[y, x] = cur
                while q:
                    cy, cx = q.popleft()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy+dy, cx+dx
                            if 0 <= ny < H and 0 <= nx < Wd and A[ny, nx] and lab[ny, nx] == 0:
                                lab[ny, nx] = cur; q.append((ny, nx))
    bx = []
    for c in range(1, cur+1):
        ys, xs = np.where(lab == c)
        if len(xs) < 10: continue
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        if (x1-x0) >= 3 and (y1-y0) >= 5: bx.append([x0, y0, x1, y1])
    bx.sort(key=lambda b: (b[1]//14, b[0]))
    return bx

for short in ("med", "light"):
    alpha = Image.open(f"atlas_{short}.png")
    bx = blobs(alpha)
    json.dump(bx, open(f"boxes_{short}.json", "w"))
    cell, cols = 46, 22
    rows = (len(bx)+cols-1)//cols
    sheet = Image.new("RGB", (cols*cell, rows*cell), (0, 0, 0)); dr = ImageDraw.Draw(sheet)
    for idx, (x0, y0, x1, y1) in enumerate(bx):
        g = alpha.crop((x0, y0, x1+1, y1+1)); g.thumbnail((cell-14, cell-14))
        r, cc = divmod(idx, cols)
        sheet.paste(g, (cc*cell+2, r*cell+2))
        dr.text((cc*cell+1, r*cell+cell-11), str(idx), fill=(0, 255, 0))
    sheet.save(f"sheet_{short}.png")
    print(short, "glyphs", len(bx), "sheet", rows, "x", cols)
