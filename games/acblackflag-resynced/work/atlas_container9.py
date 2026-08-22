# -*- coding: utf-8 -*-
"""Phase 9: prove offsets are GFOF-relative and the file closes exactly. Final map."""
import sys, os, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
D = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = [("16243",0x88c2952a),("16245",0x88c2952b),("16248",0x88c2952c),
         ("19498",0x88cf5a5b),("19499",0x8b21454b),("19500",0x88cf5a5c),
         ("70970",0x88c902b3),("70971",0x88c902b5),("70972",0x88c902b1),
         ("70973",0x88cab006),("70974",0x88c902b0)]
data = {n: open(os.path.join(D, f"{n}_{f:08x}.bin"), "rb").read() for n, f in FILES}
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def f32(b,o): return struct.unpack_from("<f",b,o)[0]

print(f"{'file':<7}{'GFOF':>7}{'blocks':>7}{'glyphs':>8}{'chainEnd':>10}{'GFOF+minOff':>13}"
      f"{'MATCH':>7}{'GFOF+maxOff+len':>17}{'size-24':>10}{'MATCH':>7}")
print("-" * 96)
for n, _ in FILES:
    b = data[n]; g = b.find(b"GFOF"); size = len(b)
    p = g + 0x24; recs = []; nb = 0
    while p + 32 <= size:
        cnt = u32(b, p)
        if u32(b, p+28) != 0x3f800000 or any(b[p+4:p+20]): break
        if cnt > 200000 or p + 32 + 36*cnt > size: break
        for i in range(cnt):
            k = p + 32 + 36*i
            recs.append((u32(b,k+32), u16(b,k), round(f32(b,k+24)), round(f32(b,k+28))))
        nb += 1
        p = p + 32 + 36*cnt
    chainEnd = p
    offs = [r[0] for r in recs]
    mn, mx = min(offs), max(offs)
    lastLen = max(w*h for o, cp, w, h in recs if o == mx)
    a = g + mn; c = g + mx + lastLen
    print(f"{n:<7}0x{g:05x}{nb:>7}{len(recs):>8}  0x{chainEnd:06x}     0x{a:06x}"
          f"{'  OK' if a == chainEnd else ' FAIL':>7}       {c:>10}{size-24:>10}"
          f"{'  OK' if c == size-24 else ' FAIL':>7}")

print()
print("Sanity: dump the first 3 rows of glyph U+06B8's bitmap in 70970 (Arabic), W=37 H=72")
b = data["70970"]; g = b.find(b"GFOF")
k = g + 0x24 + 32          # first record of block 0
cp, w, h, off = u16(b,k), round(f32(b,k+24)), round(f32(b,k+28)), u32(b,k+32)
base = g + off
print(f"  U+{cp:04X} W={w} H={h} off={off} -> abs 0x{base:x}")
for row in range(0, 6):
    r = b[base + row*w: base + (row+1)*w]
    print("   " + "".join(" .:-=+*#%@"[min(9, v * 10 // 256)] for v in r))
print("  ... middle rows:")
for row in range(h//2, h//2 + 6):
    r = b[base + row*w: base + (row+1)*w]
    print("   " + "".join(" .:-=+*#%@"[min(9, v * 10 // 256)] for v in r))
