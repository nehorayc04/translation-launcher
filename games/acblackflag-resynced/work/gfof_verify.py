# -*- coding: utf-8 -*-
"""Cross-file verification: render a known letter from every resource at
blob_base == GFOF offset, and report Hebrew coverage."""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof_final import Gfof, ATLAS, art, script_of

def find(G, cp):
    for k, f in enumerate(G.faces):
        for r in f["recs"]:
            if r[0] == cp and int(r[6]) > 3:
                return k, r
    return None, None

def main():
    print("HEBREW coverage across all 11 GFOF resources")
    for fn in sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin")):
        G = Gfof(os.path.join(ATLAS, fn))
        heb = [r[0] for k, r in G.all_recs() if 0x590 <= r[0] < 0x600]
        pua = [r[0] for k, r in G.all_recs() if 0xE000 <= r[0] < 0xF900]
        tot = sum(f["n"] for f in G.faces)
        print(f"  {fn:26s} glyphs={tot:<5} HEBREW={len(heb):<3} PUA={[hex(x) for x in pua]} "
              f"spare(cap-{G.cap})={G.cap - tot}")

    print("\nrender check at blob_base == GFOF offset (should read as the letter):")
    for fn in sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin")):
        G = Gfof(os.path.join(ATLAS, fn))
        k, r = find(G, ord("E"))
        if r is None:
            k, r = find(G, ord("A"))
        if r is None:
            print(f"  {fn}: no latin"); continue
        px, w, h = G.bitmap(r)
        print(f"\n-- {fn}  face{k} U+{r[0]:04X} {w}x{h} adv={r[1]:.2f} --")
        print(art(px, w, h, maxw=36))

if __name__ == "__main__":
    main()
