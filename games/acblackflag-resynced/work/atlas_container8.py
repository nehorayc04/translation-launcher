# -*- coding: utf-8 -*-
"""Phase 8: full block-chain walk (relaxed) + prove the bitmap-blob base by closing the file."""
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

print("=" * 108)
print("FULL BLOCK CHAIN  (block = [u32 count][16B zero][u32 param][u32 0][f32 1.0] + count*36)")
print("=" * 108)
for n, _ in FILES:
    b = data[n]; g = b.find(b"GFOF"); size = len(b)
    # last non-zero byte
    z = size
    while z > 0 and b[z-1] == 0: z -= 1
    p = g + 0x24
    blocks = []
    while p + 32 <= size:
        cnt = u32(b, p)
        if u32(b, p+28) != 0x3f800000: break
        if any(b[p+4:p+20]): break
        if cnt > 200000 or p + 32 + 36*cnt > size: break
        rec0 = p + 32
        offs = [u32(b, rec0+36*i+32) for i in range(cnt)]
        blocks.append(dict(hdr=p, cnt=cnt, param=u32(b, p+20), rec0=rec0,
                           end=rec0+36*cnt, offs=offs))
        p = rec0 + 36*cnt
    chainEnd = p
    allo = [o for bl in blocks for o in bl["offs"]]
    # last glyph length across all blocks (max offset record's W*H)
    lastLen = 0
    if allo:
        mx = max(allo)
        for bl in blocks:
            for i in range(bl["cnt"]):
                k = bl["rec0"] + 36*i
                if u32(b, k+32) == mx:
                    lastLen = max(lastLen, round(f32(b,k+24)) * round(f32(b,k+28)))
    print(f"\n  {n}: size=0x{size:x} lastNonZero=0x{z:x} pad={size-z}")
    for i, bl in enumerate(blocks):
        cps = [u16(b, bl["rec0"]+36*j) for j in range(min(3, bl["cnt"]))]
        print(f"     block{i}: hdr@0x{bl['hdr']:06x} count={bl['cnt']:<6d} param={bl['param']:<6d} "
              f"recs 0x{bl['rec0']:06x}..0x{bl['end']:06x} cps={[f'U+{c:04X}' for c in cps]}")
    print(f"     chainEnd=0x{chainEnd:06x}  maxOff={max(allo) if allo else 0}  lastGlyphWxH={lastLen}")
    if allo:
        implied_base = z - (max(allo) + lastLen)
        print(f"     => base implied by closing at lastNonZero: 0x{implied_base:x} ({implied_base}) "
              f"| chainEnd=0x{chainEnd:x} | MATCH={'YES' if implied_base == chainEnd else 'no, delta=%d' % (implied_base-chainEnd)}")

print()
print("=" * 108)
print("VERIFY: W*H == (next offset - this offset) across EVERY glyph of EVERY block")
print("=" * 108)
for n, _ in FILES:
    b = data[n]; g = b.find(b"GFOF"); size = len(b)
    p = g + 0x24; recs = []
    while p + 32 <= size:
        cnt = u32(b, p)
        if u32(b, p+28) != 0x3f800000 or any(b[p+4:p+20]): break
        if cnt > 200000 or p + 32 + 36*cnt > size: break
        for i in range(cnt):
            k = p + 32 + 36*i
            recs.append((u32(b,k+32), u16(b,k), round(f32(b,k+24)), round(f32(b,k+28))))
        p = p + 32 + 36*cnt
    recs.sort()
    ok = bad = skip = 0
    for j in range(len(recs)-1):
        off, cp, w, h = recs[j]
        implied = recs[j+1][0] - off
        if w*h == 0 or implied == 0: skip += 1; continue
        if implied == w*h: ok += 1
        else: bad += 1
    tot = ok + bad
    print(f"  {n}: glyphs={len(recs):5d}  W*H==impliedLen: {ok}/{tot} "
          f"({ok/tot*100 if tot else 0:.2f}%)  zero-size skipped={skip}")
