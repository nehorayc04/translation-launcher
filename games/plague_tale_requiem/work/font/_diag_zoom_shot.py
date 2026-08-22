# -*- coding: utf-8 -*-
import os
from PIL import Image, ImageOps

DIR = r"C:\Users\Nehoray_Cohen\Pictures\Screenshots"
NAME = "\u05e6\u05d9\u05dc\u05d5\u05dd \u05de\u05e1\u05da 2026-08-11 160501.png"
p = os.path.join(DIR, NAME)
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")

im = Image.open(p)
print("size", im.size)
g = ImageOps.autocontrast(im.convert("L"))
g.resize((g.width * 4, g.height * 4), Image.NEAREST).save(os.path.join(SC, "ZOOM_160501.png"))
print("saved")
