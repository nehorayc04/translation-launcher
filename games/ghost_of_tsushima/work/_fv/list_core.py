import os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE,"..","..","..","tlou2","tools"))
import dsar as R
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
for pf in ("gapack_misc_c.psarc","gapack_misc_g.psarc"):
    p=os.path.join(PD,pf)
    if not os.path.exists(p): 
        print(pf,"MISSING"); continue
    arc=R.Psarc2(p)
    fs=sorted(arc.files(), key=lambda e:-e.orig_size)
    print(f"\n== {pf}: {len(fs)} files ==")
    for e in fs[:15]:
        print(f"  {e.orig_size:>13,}  {e.path}")
    arc.d.f.close()
