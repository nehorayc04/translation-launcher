# -*- coding: utf-8 -*-
"""Phase 6: the payload blob after the glyph array, the 24-byte trailer, final section map."""
import sys, os, struct, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

D = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
FILES = [
    ("16243", 0x88c2952a), ("16245", 0x88c2952b), ("16248", 0x88c2952c),
    ("19498", 0x88cf5a5b), ("19499", 0x8b21454b), ("19500", 0x88cf5a5c),
    ("70970", 0x88c902b3), ("70971", 0x88c902b5), ("70972", 0x88c902b1),
    ("70973", 0x88cab006), ("70974", 0x88c902b0),
]
data = {}
for name, fid in FILES:
    with open(os.path.join(D, f"{name}_{fid:08x}.bin"), "rb") as f:
        data[name] = (fid, f.read())
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def f32(b,o): return struct.unpack_from("<f",b,o)[0]
def hx(b): return " ".join(f"{x:02x}" for x in b)

M = {}
for name, fid in FILES:
    b = data[name][1]
    ne = 0x20 + u32(b, 0x1c)
    g = b.find(b"GFOF")
    N = u32(b, g + 0x24)
    S = g + 68
    M[name] = dict(ne=ne, g=g, N=N, S=S, end=S + 36*N, size=len(b))

print("=" * 110)
print("A) GLYPH-DATA OFFSET u32 (record+32): monotonic? what does it index?")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]; m = M[name]
    offs = [u32(b, m["S"] + 36*i + 32) for i in range(m["N"])]
    mono = all(offs[i] <= offs[i+1] for i in range(len(offs)-1))
    blobStart = m["end"]
    blobLen = m["size"] - 24 - blobStart
    print(f"  {name}: N={m['N']} monotonicNonDecreasing={mono} min={min(offs)} max={max(offs)}")
    print(f"       arrayEnd=0x{m['end']:x} blobLen(to EOF-24)={blobLen}  max/blobLen={max(offs)/blobLen:.4f}")

print()
print("=" * 110)
print("B) WHAT SITS BETWEEN arrayEnd AND EOF — head of the region + the 24-byte trailer")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]; m = M[name]; e = m["end"]
    print(f"\n  {name}: arrayEnd=0x{e:x}")
    for r in range(0, 96, 16):
        seg = b[e+r:e+r+16]
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
        print(f"     +{r:<3d} {hx(seg):<47} |{asc}|")
    print(f"     TRAILER (last 24B): {hx(b[-24:])}")

print()
print("=" * 110)
print("C) TRAILER analysis: is it constant / all-zero across files? how much zero padding?")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]
    n = len(b); i = n
    while i > 0 and b[i-1] == 0:
        i -= 1
    print(f"  {name}: trailing zero bytes = {n-i}  (last non-zero at 0x{i-1:x}); "
          f"trailer24 all-zero={all(x==0 for x in b[-24:])}")

print()
print("=" * 110)
print("D) VERIFY the glyph offsets point INSIDE the post-array blob: decode a glyph header")
print("   for the Arabic file 70970 — dump 32 bytes at blobStart+offset for a few glyphs")
print("=" * 110)
name = "70970"
b = data[name][1]; m = M[name]
for i in (0, 1, 2, 3, 1053, 1054):
    k = m["S"] + 36*i
    cp = u16(b, k); off = u32(b, k+32)
    for base_name, base in (("arrayEnd", m["end"]),):
        a = base + off
        if a + 24 <= len(b):
            print(f"  glyph[{i}] U+{cp:04X} off={off} -> {base_name}+off = 0x{a:x}: {hx(b[a:a+24])}")

print()
print("=" * 110)
print("E) FINAL SECTION MAP (all 11)")
print("=" * 110)
print(f"  {'file':<7}{'size':>10} {'nameLen':>8} {'nend':>7} {'GFOF':>7} {'N':>6} {'arrStart':>9} "
      f"{'arrEnd':>9} {'blobLen':>10} {'tail':>5}")
for name, fid in FILES:
    m = M[name]
    print(f"  {name:<7}{m['size']:>10} {m['ne']-0x20:>8} 0x{m['ne']:05x} 0x{m['g']:05x} {m['N']:>6} "
          f"0x{m['S']:05x} 0x{m['end']:06x} {m['size']-24-m['end']:>10} {24:>5}")

print()
print("=" * 110)
print("F) THE 104 CONSTANT BYTES at nend+54..nend+157 (identical in ALL 11) — full hex")
print("=" * 110)
b = data["70970"][1]; ne = M["70970"]["ne"]
seg = b[ne+54:ne+158]
for r in range(0, len(seg), 16):
    ch = seg[r:r+16]
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
    print(f"   nend+{54+r:<4d} {hx(ch):<47} |{asc}|")

print()
print("=" * 110)
print("G) THE VARIABLE 39 BYTES at nend+158..nend+196, aligned across files")
print("=" * 110)
for name, fid in FILES:
    b = data[name][1]; ne = M[name]["ne"]
    seg = b[ne+158:ne+197]
    asc = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
    print(f"  {name}: {hx(seg)}  |{asc}|")
