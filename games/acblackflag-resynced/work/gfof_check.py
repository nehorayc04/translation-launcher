# -*- coding: utf-8 -*-
"""Sanity-check the codepoint<->bitmap pairing using ASCII width intuition."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof_faces import walk, rd, ATLAS, REC

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else "70970"
    fn = [f for f in sorted(os.listdir(ATLAS)) if sel in f and f.endswith(".bin")][0]
    data = open(os.path.join(ATLAS, fn), "rb").read()
    g = data.find(b"GFOF")
    faces = walk(data, g + 0x48)
    for fi, f in enumerate(faces):
        recs = [rd(data, f["rec_start"] + i*REC) for i in range(f["n"])]
        ascii_recs = [(i, r) for i, r in enumerate(recs) if 0x20 <= r[8] < 0x7F]
        if len(ascii_recs) < 20: continue
        print(f"=== face{fi}  n={f['n']}  ASCII entries={len(ascii_recs)} ===")
        cps = [r[8] for _, r in ascii_recs]
        print(f"    duplicate ASCII cps: {len(cps)-len(set(cps))}")
        by = {r[8]: (i, r) for i, r in ascii_recs}
        for cp in [0x2E, 0x27, 0x21, 0x49, 0x69, 0x6C, 0x57, 0x4D, 0x41, 0x42, 0x4F, 0x6F, 0x30, 0x5F]:
            if cp in by:
                i, r = by[cp]
                print(f"    U+{cp:04X} '{chr(cp)}'  rec#{i:<4} w={int(r[5]):>3} h={int(r[6]):>3} "
                      f"adv={r[0]:>7.2f} box=({r[1]:>7.2f},{r[2]:>7.2f})-({r[3]:>7.2f},{r[4]:>7.2f})")
        print()

if __name__ == "__main__":
    main()
