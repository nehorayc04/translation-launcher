# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, ".")
from dpc_repack import DpcRepack
from fonts_z import FontsZ, cid_to_char
DPC = r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC"
BIG = 0xAFBE3792DDA3B358
D = DpcRepack(DPC + ".he_backup")
byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
fz = FontsZ(byid[BIG].body)
def show(e):
    c = cid_to_char(e.cid)
    print(f"  '{c}' cid={e.cid:04X} mat={e.mat} adv={e.adv:.2f} box=({e.x0:.1f},{e.y0:.1f})-({e.x1:.1f},{e.y1:.1f}) "
          f"w={e.x1-e.x0:.1f} h={e.y1-e.y0:.1f} bx={e.bx:.2f} by={e.by:.2f} z={e.z}")
print("== Latin/ASCII reference glyphs ==")
for ch in "ACENO@ilotw█":
    e = fz.by_char(ch)
    if e: show(e)
# all non-arabic single-char latin letters present
def is_ar(cp): return 0x0600<=cp<=0x06FF or 0xFB50<=cp<=0xFEFF
latins = sorted({cid_to_char(e.cid) for e in fz.entries if len(cid_to_char(e.cid))==1 and cid_to_char(e.cid).isascii() and cid_to_char(e.cid).isprintable()})
print("\nASCII glyphs available:", "".join(latins))
# show a lowercase-ish set to find baseline vs cap
print("\n== sample of ALL entries by y-range (first 12 non-arabic) ==")
n=0
for e in fz.entries:
    c=cid_to_char(e.cid)
    if c and not is_ar(ord(c[0])):
        show(e); n+=1
        if n>=12: break
# arabic slots we'd repurpose: count + size distribution
ars=[e for e in fz.entries if (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid))]
print(f"\narabic entries: {len(ars)}; box widths:", sorted(int(e.x1-e.x0) for e in ars)[:30])
