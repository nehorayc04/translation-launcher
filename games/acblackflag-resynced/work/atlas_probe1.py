# -*- coding: utf-8 -*-
"""Phase 1: structural recon of the 0xcbd4939a atlas resources.
- hexdump heads
- entropy map (per 4KB block) to find low-entropy structured regions
- ASCII string extraction
"""
import os, sys, math, json, collections

ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin"))

def hexdump(b, base=0, n=256, width=16):
    out = []
    for i in range(0, min(n, len(b)), width):
        ch = b[i:i+width]
        hx = " ".join(f"{c:02x}" for c in ch)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
        out.append(f"{base+i:08x}  {hx:<{width*3}} |{asc}|")
    return "\n".join(out)

def entropy(b):
    if not b: return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v/n)*math.log2(v/n) for v in c.values())

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    for fn in FILES:
        if target and target not in fn: continue
        p = os.path.join(ATLAS, fn)
        data = open(p, "rb").read()
        print("="*100)
        print(f"{fn}  size={len(data)} (0x{len(data):x})")
        print("-- head 512 --")
        print(hexdump(data[:512], 0, 512))
        print("-- tail 256 --")
        print(hexdump(data[-256:], len(data)-256, 256))
        # entropy map, 4KB blocks
        BS = 4096
        ent = []
        for off in range(0, len(data), BS):
            ent.append(entropy(data[off:off+BS]))
        print(f"-- entropy map: {len(ent)} blocks of {BS}B --")
        # print compressed run-length summary: bucket entropy into 1 char
        chars = "0123456789"
        line = "".join(chars[min(9, int(e))] for e in ent)
        for i in range(0, len(line), 100):
            print(f"  blk {i:6d} (@0x{i*BS:08x}): {line[i:i+100]}")
        # lowest entropy blocks
        idx = sorted(range(len(ent)), key=lambda i: ent[i])[:15]
        print("-- 15 lowest-entropy blocks --")
        for i in sorted(idx):
            print(f"   blk {i} @0x{i*BS:08x} ent={ent[i]:.3f}")
        print(f"-- mean entropy {sum(ent)/len(ent):.3f} --")

if __name__ == "__main__":
    main()
