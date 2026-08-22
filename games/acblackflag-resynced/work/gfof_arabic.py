# -*- coding: utf-8 -*-
"""Final report data for the Arabic atlas 70970 + exact record semantics."""
import os, sys, json, collections, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof_final import Gfof, ATLAS, art, script_of

G = Gfof(os.path.join(ATLAS, "70970_88c902b3.bin"))
print(f"GFOF@0x{G.g:x} cap={G.cap} pxsize={G.pxsize} asc={G.ascent} desc={G.descent}")
print(f"padX(GFOF+0x1c)={struct.unpack_from('<I', G.data, G.g+0x1c)[0]} "
      f"padY(GFOF+0x20)={struct.unpack_from('<I', G.data, G.g+0x20)[0]}")

print("\n-- exact records, face0 (Arabic) first 8 --")
print(f"{'#':>4} {'cp':>8} {'adv':>8} {'x0':>8} {'y0':>8} {'x1':>8} {'y1':>8} {'w':>5} {'h':>5} {'boff':>10} {'x1-x0':>7} {'y1-y0':>7}")
for i, r in enumerate(G.faces[0]["recs"][:8]):
    cp, adv, x0, y0, x1, y1, w, h, bo = r
    print(f"{i:>4} U+{cp:04X} {adv:>8.2f} {x0:>8.2f} {y0:>8.2f} {x1:>8.2f} {y1:>8.2f} "
          f"{int(w):>5} {int(h):>5} {bo:>10} {x1-x0:>7.2f} {y1-y0:>7.2f}")

f0 = G.faces[0]["recs"]
cps = sorted(r[0] for r in f0)
print(f"\nface0 (Arabic face): {len(cps)} glyphs, {len(set(cps))} unique")
buck = collections.defaultdict(list)
for c in cps: buck[script_of(c)].append(c)
for k, v in sorted(buck.items(), key=lambda kv: -len(kv[1])):
    print(f"   {k:14s} {len(v):>4}  U+{min(v):04X}..U+{max(v):04X}")
print(f"   ASCII members: {[hex(c) for c in buck.get('ASCII', [])]}")
print(f"   Arabic block coverage U+0600-06FF: {len(buck['Arabic'])}/256")
missing = [c for c in range(0x0600, 0x0700) if c not in set(cps)]
print(f"   missing from U+0600-06FF: {len(missing)} -> {[hex(c) for c in missing[:12]]}")

# max glyph box in the whole file (repack budget)
allr = [r for k, r in G.all_recs()]
print(f"\nblob: base=0x{G.blob_base:x} start=0x{G.blob_base+min(r[8] for r in allr):x} "
      f"end=0x{G.blob_base+max(r[8]+int(r[6])*int(r[7]) for r in allr):x} EOF=0x{len(G.data):x}")
print(f"bytes before blob (headers+tables) = {min(r[8] for r in allr)} ; metaEnd=0x{G.meta_end:x} "
      f"gap={G.blob_base+min(r[8] for r in allr)-G.meta_end}")

# render an arabic letter to prove the face is really arabic
for r in f0:
    if r[0] == 0x0645 and int(r[6]) > 5:      # ARABIC LETTER MEEM
        px, w, h = G.bitmap(r)
        print(f"\n-- U+0645 MEEM {w}x{h} adv={r[1]:.2f} --")
        print(art(px, w, h, maxw=44))
        break

out = os.path.join(os.path.dirname(ATLAS), "gfof_70970_face0_codepoints.json")
json.dump({"file": "70970_88c902b3.bin", "face": 0, "count": len(cps),
           "codepoints": [f"U+{c:04X}" for c in cps]}, open(out, "w"), indent=1)
print(f"\nwrote {out}")
