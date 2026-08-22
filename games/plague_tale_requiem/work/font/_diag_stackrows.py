# -*- coding: utf-8 -*-
import os, glob
from PIL import Image, ImageOps

SHOTS = r"C:\Users\Nehoray_Cohen\Pictures\Screenshots"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")

shot = sorted(glob.glob(os.path.join(SHOTS, "*.png")), key=os.path.getmtime)[-1]
im = Image.open(shot)
print(shot, im.size)

bands = [(272, 310), (356, 374), (427, 445), (496, 511), (568, 586),
         (639, 653), (709, 723), (761, 777), (798, 812)]
row = []
for a, b in bands:
    c = im.crop((320, a - 3, 512, b + 3)).convert("L")
    c = ImageOps.autocontrast(c)
    c = c.resize((c.width * 5, c.height * 5), Image.NEAREST)
    row.append(c)
Wm = max(c.width for c in row)
Hs = sum(c.height + 10 for c in row)
canvas = Image.new("L", (Wm, Hs), 255)
y = 0
for c in row:
    canvas.paste(c, (0, y))
    y += c.height + 10
canvas.save(os.path.join(SC, "ROWS_stacked.png"))
print("saved", canvas.size)
