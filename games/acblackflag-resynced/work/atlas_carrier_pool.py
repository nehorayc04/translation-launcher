# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work")
from gfof_final import Gfof, ATLAS

A = Gfof(os.path.join(ATLAS, "70970_88c902b3.bin"))
cached_all = set(r[0] for k, r in A.all_recs())
face0 = set(r[0] for r in A.faces[0]["recs"])
print("arabic atlas 70970: total cached cps =", len(cached_all), " face0 =", len(face0))

# ranges of interest
rngs = {"Arabic 0600-06FF": (0x0600,0x0700), "ArabicSuppl 0750-077F": (0x0750,0x0780),
        "ArabExtB 0870-089F": (0x0870,0x08A0), "ArabExtA 08A0-08FF": (0x08A0,0x0900),
        "PresA FB50-FDFF": (0xFB50,0xFE00), "PresB FE70-FEFF": (0xFE70,0xFF00)}
absent = {}
for name,(a,b) in rngs.items():
    pres = [c for c in range(a,b) if c in cached_all]
    ab   = [c for c in range(a,b) if c not in cached_all]
    absent[name] = ab
    print(f"  {name:24s} cached={len(pres):>4}  absent={len(ab):>4}")

# unicode props via unicodedata
import unicodedata as ud
def bidi(c): return ud.bidirectional(chr(c))
def cat(c):  return ud.category(chr(c))

# joining type: derive non-joining set from unicodedata? not available -> use static list of Joining_Type U for arabic block
NONJOIN_BLOCK = [0x0608,0x060B,0x060D,0x061B,0x061D,0x061E,0x061F,0x0621,0x066D,0x0674,0x06D4,0x06E5,0x06E6,0x06FD,0x06FE]
print("\nnon-joining AL in 0600-06FF, NOT in arabic atlas cache:",
      [hex(c) for c in NONJOIN_BLOCK if c not in cached_all])
print("non-joining AL in 0600-06FF, IN cache (cache-hit, unusable as raster carrier):",
      [hex(c) for c in NONJOIN_BLOCK if c in cached_all])

# presentation forms are ALL joining_type=U
pfa_abs = [c for c in absent["PresA FB50-FDFF"] if bidi(c)=='AL' and not cat(c).startswith(('C','M'))]
pfb_abs = [c for c in absent["PresB FE70-FEFF"] if bidi(c)=='AL' and not cat(c).startswith(('C','M'))]
print(f"\nPOOL: PresA absent+AL+spacing = {len(pfa_abs)} -> {[hex(c) for c in pfa_abs[:20]]}")
print(f"POOL: PresB absent+AL+spacing = {len(pfb_abs)} -> {[hex(c) for c in pfb_abs]}")
exta = [c for c in range(0x0870,0x0900) if c not in cached_all and bidi(c)=='AL' and not cat(c).startswith(('C','M'))]
print(f"POOL: ExtA/B absent+AL+spacing = {len(exta)} -> {[hex(c) for c in exta[:30]]}")
