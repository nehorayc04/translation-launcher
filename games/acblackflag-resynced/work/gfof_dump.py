# -*- coding: utf-8 -*-
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfof import parse, ATLAS, HDR, REC, FMT

def hexdump(b, base=0, width=16):
    out = []
    for i in range(0, len(b), width):
        ch = b[i:i+width]
        hx = " ".join(f"{c:02x}" for c in ch)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
        out.append(f"{base+i:08x}  {hx:<{width*3}} |{asc}|")
    return "\n".join(out)

def main():
    sel = sys.argv[1]
    lo  = int(sys.argv[2]); hi = int(sys.argv[3])
    fn = [f for f in sorted(os.listdir(ATLAS)) if sel in f and f.endswith(".bin")][0]
    r = parse(os.path.join(ATLAS, fn))
    print(f"{fn} GFOF@0x{r['gfof']:x} tbl=0x{r['tbl']:x} n={r['n']}")
    print(f"{'idx':>5} {'@off':>8} {'cp':>7} {'char':4} {'adv':>9} {'x0':>8} {'y0':>8} {'x1':>8} {'y1':>8} {'w':>6} {'h':>6} {'boff':>10} {'w*h':>8} {'next?':>10}")
    for rc in r["recs"][lo:hi]:
        cp = rc["cp"]
        try: ch = chr(cp) if 32 < cp < 0x110000 else "?"
        except Exception: ch = "?"
        if not (0x20 < cp < 0x110000): ch = "."
        print(f"{rc['i']:>5} 0x{rc['off']:06x} {cp:>7} U+{cp:04X} {rc['adv']:>9.3f} {rc['x0']:>8.3f} {rc['y0']:>8.3f} "
              f"{rc['x1']:>8.3f} {rc['y1']:>8.3f} {rc['w']:>6.1f} {rc['h']:>6.1f} {rc['boff']:>10} "
              f"{int(rc['w'])*int(rc['h']):>8} {rc['boff']+int(rc['w'])*int(rc['h']):>10}")
    if len(sys.argv) > 4:
        a = int(sys.argv[4], 0); b = int(sys.argv[5], 0)
        print("\n-- raw --")
        print(hexdump(r["data"][a:b], a))

if __name__ == "__main__":
    main()
