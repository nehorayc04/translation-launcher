# -*- coding: utf-8 -*-
r"""store_s16.py — test whether the FontVerts tail is s16 FIXED-POINT coords, not f32.

The 47% 'high-entropy OTHER' under an f32 lens is the classic symptom of a WRONG lens.
The 114x-repeated notdef unit 52e7db495a83c351 decodes as garbage f32 but as
4x s16/32768 = (-0.19,0.58),(-0.97,0.64) = plausible normalized coords. If the whole
tail is >90% in-range under some s16 scale, the coord codec is CRACKED (it's s16 fixed).
"""
import struct

F = open("extract/ghost_title.xpps", "rb").read()
N = len(F)
STORE = 0x97c8d0
tail = F[STORE:]
print(f"tail {len(tail):,} B  ({len(tail)//2:,} s16 samples)")

s16 = struct.unpack_from(f"<{len(tail)//2}h", tail, 0)
u16 = struct.unpack_from(f"<{len(tail)//2}H", tail, 0)


def frac_in_range(vals, scale, lo=-1.05, hi=1.05):
    inr = sum(1 for v in vals if lo <= v / scale <= hi)
    return inr / len(vals)


print("\n== s16 fixed-point: fraction of ALL s16 samples in [-1.05,1.05] ==")
for scale, name in [(32768, "s16/32768 (1.15)"), (16384, "s16/16384 (2.14)"),
                    (4096, "s16/4096 (4.12)"), (256, "s16/256 (8.8)"),
                    (1024, "s16/1024 (6.10)"), (2048, "s16/2048")]:
    print(f"  {name:22} in-range={frac_in_range(s16, scale)*100:5.1f}%")

print("\n== u16 fixed (0..1): fraction in [0,1.05] ==")
for scale, name in [(65535, "u16/65535"), (32768, "u16/32768"), (16384, "u16/16384")]:
    inr = sum(1 for v in u16 if v / scale <= 1.05) / len(u16)
    print(f"  {name:16} in-range={inr*100:5.1f}%")

# decode the notdef box units under s16/32768
print("\n== notdef-box repeated units as s16/32768 pairs ==")
for hx in ["52e7db495a83c351", "34387f596c80d90f", "4ce0bb998e8afc04", "ee64f270b53cf0a0"]:
    b = bytes.fromhex(hx)
    a, c, d, e = struct.unpack("<4h", b)
    print(f"  {hx} -> ({a/32768:+.3f},{c/32768:+.3f}) ({d/32768:+.3f},{e/32768:+.3f})")

# first CLEAN-as-f32 run @0x97c8d0: does it ALSO read sane as s16?
print("\n== first run @store as s16/32768 (was clean under f32) ==")
for i in range(8):
    a, c = s16[i * 2], s16[i * 2 + 1]
    fa, fc = struct.unpack_from("<2f", tail, i * 8)
    print(f"  s16=({a/32768:+.3f},{c/32768:+.3f})   f32=({fa:+.3f},{fc:+.3f})")

# histogram: how contiguous are the in-range s16 samples? (real coords cluster)
print("\n== run-length of consecutive in-range s16/32768 samples (top buckets) ==")
import collections
run = 0
buckets = collections.Counter()
for v in s16:
    if -1.05 <= v / 32768 <= 1.05:
        run += 1
    else:
        if run:
            buckets[min(run, 64)] += 1
        run = 0
if run:
    buckets[min(run, 64)] += 1
for rl in sorted(buckets)[:20]:
    print(f"  run-len {rl:3}: {buckets[rl]}")
