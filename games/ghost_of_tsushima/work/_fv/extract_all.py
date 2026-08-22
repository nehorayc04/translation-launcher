# extract the font-bearing .xpps to scratch for fast iteration
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE,"..","..","..","tlou2","tools"))
import dsar as R
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
OUT=HERE
targets=[
 ("gapack_misc_m.psarc","m_lm_menu.sprig.xpps"),
]
for arc_name, fname in targets:
    arc=R.Psarc2(os.path.join(PD,arc_name))
    t=next((e for e in arc.files() if e.path.rstrip('/').endswith(fname)),None)
    if not t:
        print("MISSING",fname); continue
    d=arc.extract(t); arc.d.f.close()
    op=os.path.join(OUT,fname)
    open(op,"wb").write(d)
    print(f"wrote {len(d):,}B  {op}  (from {arc.path} :: {t.path})")
