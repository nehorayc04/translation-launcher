# -*- coding: utf-8 -*-
import sys, struct, unicodedata
sys.path.insert(0,".")
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
DPC=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
D=DpcRepack(DPC+".he_backup")
allobj=list(D.db_objs)+[o for _,o,_ in D.fb_objs]
FONT_OT=0x87218B06F6FE91FD
fonts=[o for o in allobj if o.otype==FONT_OT]
BIG=0xAFBE3792DDA3B358
def name_of(cp):
    try: return unicodedata.name(chr(cp))
    except: return "?"
def is_ar_letter(cp): return 0x0620<=cp<=0x064A or 0x0660<=cp<=0x066D or 0xFB50<=cp<=0xFEFF
for o in fonts:
    fz=FontsZ(o.body)
    ar=[]
    for e in fz.entries:
        c=cid_to_char(e.cid)
        if not c: continue
        cp=ord(c[0])
        if 0x0600<=cp<=0x06FF or 0xFB50<=cp<=0xFEFF:
            ar.append(cp)
    # classify: letters (0620-064A / FB50-FEFF presentation) vs digits (0660-0669) vs punct
    letters=[cp for cp in ar if (0x0620<=cp<=0x064A) or (0xFB50<=cp<=0xFEFF)]
    digits=[cp for cp in ar if 0x0660<=cp<=0x0669]
    other=[cp for cp in ar if cp not in letters and cp not in digits]
    tag="  <-- BIG_ARABIC" if o.oid==BIG else ""
    print(f"{o.oid:016X} ar_total={len(ar):3} letters={len(letters):3} digits={len(digits)} other={len(other)}{tag}")
    if 0<len(ar)<=12:
        print("      codepoints:", ", ".join(f"U+{cp:04X}({name_of(cp)[:22]})" for cp in ar))
# also: does BIG_ARABIC have duplicate letters (same char twice = multi-size)?
fzb=FontsZ(next(o for o in fonts if o.oid==BIG).body)
from collections import Counter
cc=Counter(cid_to_char(e.cid) for e in fzb.entries)
dups={k:v for k,v in cc.items() if v>1}
print("\nBIG_ARABIC duplicate chars (same letter multiple sizes?):", dict(list(dups.items())[:20]) or "NONE")
