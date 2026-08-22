# -*- coding: utf-8 -*-
import sys, struct
sys.path.insert(0,".")
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
DPC=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
D=DpcRepack(DPC+".he_backup")
allobj=list(D.db_objs)+[o for _,o,_ in D.fb_objs]
BIG=0xAFBE3792DDA3B358
FONT_OTYPE=next(o.otype for o in allobj if o.oid==BIG)
print("Fonts_Z otype = %016X"%FONT_OTYPE)
fonts=[o for o in allobj if o.otype==FONT_OTYPE]
print(f"{len(fonts)} Fonts_Z objects in ENGLISH.DPC:\n")
for o in fonts:
    try:
        fz=FontsZ(o.body)
        # glyph height stats
        hs=sorted(int(e.y1-e.y0) for e in fz.entries if e.y1>e.y0)
        med=hs[len(hs)//2] if hs else 0
        # how many latin / arabic / hebrew
        def cls(e):
            c=cid_to_char(e.cid)
            if not c: return "?"
            cp=ord(c[0])
            if 0x0600<=cp<=0x06FF or 0xFB50<=cp<=0xFEFF: return "ar"
            if 0x05D0<=cp<=0x05EA: return "he"
            if cp<128: return "lat"
            return "oth"
        from collections import Counter
        cc=Counter(cls(e) for e in fz.entries)
        tag = "BIG_ARABIC(injected)" if o.oid==BIG else ""
        print(f" id={o.oid:016X} glyphs={fz.count:3} h[min/med/max]={hs[0] if hs else 0}/{med}/{hs[-1] if hs else 0} {dict(cc)} {tag}")
    except Exception as e:
        print(f" id={o.oid:016X} parse-fail: {e}")
