#!/usr/bin/env python3
"""Recover stream B by SCANNING region B for 36-byte glyph records and chain-verifying
them against the raster-contiguity invariant (tex_{i+1} == tex_i + W_i*H_i)."""
import os, sys, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acbf_phxfd import load, parse, FILES, blockname


def scan(d, lo, hi, texlo, texhi):
    """Every byte offset in [lo,hi) that reads as a plausible glyph record."""
    out = {}
    for o in range(lo, hi - 36):
        tex, cp = struct.unpack_from("<II", d, o + 28)
        if not (texlo <= tex < texhi):
            continue
        if not (1 <= cp <= 0x10FFFF):
            continue
        m = struct.unpack_from("<7f", d, o)
        w, h = m[5], m[6]
        if not (0.0 <= w < 512 and 0.0 <= h < 512):
            continue
        if abs(w - round(w)) > 1e-3 or abs(h - round(h)) > 1e-3:
            continue
        if not (-300 < m[1] < 300 and -300 < m[2] < 300 and 0 <= m[0] < 512):
            continue
        out[o] = dict(o=o, adv=m[0], xmin=m[1], ymin=m[2], xmax=m[3], ymax=m[4],
                      w=int(round(w)), h=int(round(h)), tex=tex, cp=cp)
    return out


def chain(cands, start_tex, end_tex):
    """Walk the raster region: at each position take the candidate record whose tex matches."""
    bytex = collections.defaultdict(list)
    for r in cands.values():
        bytex[r["tex"]].append(r)
    pos = start_tex
    got = []
    while pos < end_tex:
        c = bytex.get(pos)
        if not c:
            break
        # prefer the candidate at the smallest offset not already used
        r = sorted(c, key=lambda x: x["o"])[0]
        got.append(r)
        step = r["w"] * r["h"]
        if step <= 0:
            break
        pos += step
    return got, pos


def main():
    for n in FILES:
        d = load(n)
        hdrA, recsA = parse(d)
        firstA = min(r["tex"] for r in recsA)
        lastA = max(r["tex"] + int(round(r["w"])) * int(round(r["h"])) for r in recsA)
        cands = scan(d, hdrA["rec_end"], firstA, lastA, len(d) + 1)
        got, pos = chain(cands, lastA, len(d))
        px = sum(r["w"] * r["h"] for r in got)
        used = {r["o"] for r in got}
        span_lo, span_hi = (min(used), max(used) + 36) if used else (0, 0)
        blocks = collections.Counter(blockname(r["cp"]) for r in got)
        heb = [r for r in got if 0x590 <= r["cp"] <= 0x5FF]
        print(f"\n=== {n} ({len(d):,} B) ===")
        print(f"  A: {hdrA['count']} glyphs  raster 0x{firstA:x}..0x{lastA:x} ({lastA-firstA:,} B)")
        print(f"  B: candidates={len(cands)}  CHAINED={len(got)} glyphs  raster 0x{lastA:x}..0x{pos:x} "
              f"({px:,} B)")
        print(f"     B records occupy 0x{span_lo:x}..0x{span_hi:x} inside region B "
              f"(0x{hdrA['rec_end']:x}..0x{firstA:x}, {firstA-hdrA['rec_end']:,} B)")
        print(f"     chain stopped at 0x{pos:x}; file end 0x{len(d):x}; REMAINDER {len(d)-pos:,} B")
        print(f"     B blocks: " + ", ".join(f"{k}={v}" for k, v in blocks.most_common(8)))
        print(f"     TOTAL accounted = 0x{firstA:x} + {lastA-firstA:,} + {px:,} = "
              f"{firstA + (lastA-firstA) + px:,} of {len(d):,}  -> unexplained {len(d)-(firstA+(lastA-firstA)+px):,}")
        print(f"     HEBREW in B: {len(heb)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
