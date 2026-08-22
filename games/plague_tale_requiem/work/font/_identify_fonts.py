# -*- coding: utf-8 -*-
import sys, struct
sys.path.insert(0,".")
import numpy as np
from PIL import Image
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char, char_to_cid
from build_hebrew_font import decode_alpha, TEX_CLASS, NPIX
DPC=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
SC=r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad"
D=DpcRepack(DPC+".he_backup")
allobj=list(D.db_objs)+[o for _,o,_ in D.fb_objs]
byid={o.oid:o for o in allobj}
FONT_OT=0x87218B06F6FE91FD
fonts=[o for o in allobj if o.otype==FONT_OT]
texids={o.oid for o in allobj if o.otype==TEX_CLASS}

def mat_textures(fz):
    mc=struct.unpack_from("<I",fz.tail,0)[0]
    mats=list(struct.unpack_from("<%dQ"%mc,fz.tail,4))
    m2t={}
    for i,mid in enumerate(mats):
        o=byid.get(mid)
        if not o: continue
        b=o.info+o.body
        for off in range(0,len(b)-8):
            v=struct.unpack_from("<Q",b,off)[0]
            if v in texids: m2t[i]=v; break
    return m2t

sample="SELECTao"
rows=[]
labels=[]
for o in fonts:
    fz=FontsZ(o.body); m2t=mat_textures(fz)
    strip=Image.new("L",(len(sample)*70+10,90),20)
    x=5
    for ch in sample:
        e=fz.by_char(ch)
        if e and e.mat in m2t:
            a=decode_alpha(bytearray(byid[m2t[e.mat]].body[:NPIX]))
            crop=a[int(e.y0):int(e.y1),int(e.x0):int(e.x1)]
            im=Image.fromarray(crop,"L")
            h=min(80,crop.shape[0]); w=int(crop.shape[1]*h/max(1,crop.shape[0]))
            im=im.resize((max(1,w),h))
            strip.paste(im,(x,5))
        x+=70
    rows.append(strip); labels.append("%016X n=%d"%(o.oid,fz.count))
# stack
from PIL import ImageDraw, ImageFont
f=ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf",20)
W=max(r.width for r in rows)+320; H=sum(r.height for r in rows)+20
sheet=Image.new("RGB",(W,H),(30,30,30)); d=ImageDraw.Draw(sheet)
y=10
for r,lab in zip(rows,labels):
    sheet.paste(r.convert("RGB"),(310,y))
    d.text((8,y+30),lab,font=f,fill=(220,220,180))
    y+=r.height
p=f"{SC}/font_styles.png"; sheet.save(p); print("saved",p)
