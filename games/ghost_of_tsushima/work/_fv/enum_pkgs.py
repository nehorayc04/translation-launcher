import os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE,"..","..","..","tlou2","tools"))
import dsar as R
GAME=r"F:/Games/Ghost of Tsushima DC"; PD=os.path.join(GAME,"cache_pc","psarc")
psarcs=[f for f in os.listdir(PD) if f.endswith(".psarc")]
print(f"{len(psarcs)} psarcs")
hits=[]
for pf in sorted(psarcs):
    try:
        arc=R.Psarc2(os.path.join(PD,pf))
    except Exception as e:
        print(f"  {pf}: ERR {e}"); continue
    files=arc.files()
    arc.d.f.close()
    # font-ish names
    for e in files:
        p=e.path.lower()
        if "font" in p or "glyph" in p or "sfont" in p:
            hits.append((pf,e.path,e.orig_size))
    # small .xpps with 'font' or interesting
print(f"\n== font/glyph-named entries ==")
for pf,p,sz in hits:
    print(f"  {pf} :: {p}  ({sz:,}B)")
