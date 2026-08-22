#!/usr/bin/env python3
"""Resolve ALL glyph streams in a PHXFD atlas and account for every byte.

Method: collect every plausible 36-byte glyph record in the table region, then repeatedly
walk the raster area with the contiguity invariant tex_{i+1} == tex_i + W_i*H_i, restarting
at the next available candidate tex whenever a chain stalls."""
import os, sys, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acbf_phxfd import load, parse, FILES, blockname


def scan(d, lo, hi, texlo, texhi):
    out = []
    for o in range(lo, hi - 36):
        tex, cp = struct.unpack_from("<II", d, o + 28)
        if not (texlo <= tex < texhi) or not (1 <= cp <= 0x10FFFF):
            continue
        m = struct.unpack_from("<7f", d, o)
        w, h = m[5], m[6]
        if not (0.0 <= w < 512 and 0.0 <= h < 512):
            continue
        if abs(w - round(w)) > 1e-3 or abs(h - round(h)) > 1e-3:
            continue
        if not (-300 < m[1] < 300 and -300 < m[2] < 300 and 0 <= m[0] < 512):
            continue
        out.append(dict(o=o, adv=m[0], xmin=m[1], ymin=m[2], xmax=m[3], ymax=m[4],
                        w=int(round(w)), h=int(round(h)), tex=tex, cp=cp))
    return out


def resolve(d):
    hdrA, recsA = parse(d)
    firstA = min(r["tex"] for r in recsA)
    lastA = max(r["tex"] + int(round(r["w"])) * int(round(r["h"])) for r in recsA)
    cands = scan(d, hdrA["rec_end"], firstA, lastA, len(d) + 1)
    bytex = collections.defaultdict(list)
    for r in cands:
        bytex[r["tex"]].append(r)
    used_off = set()
    streams = []
    pos = lastA
    while pos < len(d):
        cs = [r for r in bytex.get(pos, []) if r["o"] not in used_off]
        if not cs:
            nxt = sorted(t for t in bytex if t > pos and any(r["o"] not in used_off for r in bytex[t]))
            if not nxt:
                break
            streams.append(dict(kind="GAP", start=pos, end=nxt[0], n=0, recs=[]))
            pos = nxt[0]
            continue
        chain = []
        start = pos
        while pos < len(d):
            cs = [r for r in bytex.get(pos, []) if r["o"] not in used_off]
            if not cs:
                break
            r = sorted(cs, key=lambda x: x["o"])[0]
            used_off.add(r["o"])
            chain.append(r)
            step = r["w"] * r["h"]
            if step <= 0:
                break
            pos += step
        streams.append(dict(kind="STREAM", start=start, end=pos, n=len(chain), recs=chain))
    return hdrA, recsA, firstA, lastA, streams


def main():
    for n in (FILES if len(sys.argv) < 2 else [sys.argv[1]]):
        d = load(n)
        hdrA, recsA, firstA, lastA, streams = resolve(d)
        print(f"\n{'='*78}\n=== {n} ({len(d):,} B) ===")
        blocksA = collections.Counter(blockname(r["cp"]) for r in recsA)
        print(f"  header+tables : 0x0 .. 0x{firstA:x}  ({firstA:,} B)")
        print(f"  STREAM A      : 0x{firstA:x}..0x{lastA:x} ({lastA-firstA:,} B) "
              f"{hdrA['count']} glyphs  {dict(list(blocksA.most_common(4)))}")
        tot = lastA
        for i, s in enumerate(streams):
            if s["kind"] == "GAP":
                print(f"  ---- GAP ---- : 0x{s['start']:x}..0x{s['end']:x} ({s['end']-s['start']:,} B)")
                continue
            b = collections.Counter(blockname(r["cp"]) for r in s["recs"])
            heb = sum(1 for r in s["recs"] if 0x590 <= r["cp"] <= 0x5FF)
            print(f"  STREAM {chr(66+i)}      : 0x{s['start']:x}..0x{s['end']:x} ({s['end']-s['start']:,} B) "
                  f"{s['n']} glyphs  {dict(list(b.most_common(4)))}  HEB={heb}")
            tot = s["end"]
        print(f"  after last stream: 0x{tot:x}..0x{len(d):x} = {len(d)-tot:,} B unaccounted "
              f"({100*(len(d)-tot)/len(d):.2f}%)")
        if len(d) - tot > 0:
            print(f"    trailing bytes head: {d[tot:tot+32].hex()}")
            print(f"    trailing zero%: {100*d[tot:].count(0)/(len(d)-tot):.1f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
