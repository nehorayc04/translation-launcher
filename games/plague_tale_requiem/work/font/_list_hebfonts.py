# -*- coding: utf-8 -*-
import glob, os
from PIL import ImageFont
from fontTools.ttLib import TTFont, TTCollection
def has_hebrew(path, idx=0):
    try:
        f = TTFont(path, fontNumber=idx) if path.lower().endswith(('.ttc','.otc')) else TTFont(path)
        for t in f['cmap'].tables:
            if 0x05D0 in t.cmap and 0x05EA in t.cmap:
                name=""
                for rec in f['name'].names:
                    if rec.nameID==4:
                        try: name=rec.toUnicode(); break
                        except: pass
                return name or os.path.basename(path)
    except Exception:
        return None
    return None
found=[]
for p in sorted(glob.glob(r"C:\Windows\Fonts\*.ttf")+glob.glob(r"C:\Windows\Fonts\*.otf")):
    n=has_hebrew(p)
    if n: found.append((os.path.basename(p), n))
for p in sorted(glob.glob(r"C:\Windows\Fonts\*.ttc")):
    try:
        c=TTCollection(p)
        for i in range(len(c.fonts)):
            n=has_hebrew(p,i)
            if n: found.append((os.path.basename(p)+f"#{i}", n)); break
    except: pass
print(f"{len(found)} Hebrew-capable fonts:")
for fn,nm in found: print(f"  {fn:22} {nm}")
