# -*- coding: utf-8 -*-
"""GFOF (Anvil baked-glyph font) parser + validator.

Layout hypothesis under test
----------------------------
  <resource header ...>  'GFOF' magic
  GFOF+0x00  char[4]  'GFOF'
  GFOF+0x04  u32      glyphCount
  GFOF+0x08  f32      ?
  GFOF+0x0c  f32      ?
  GFOF+0x10  u32      ?  (40 = px size?)
  GFOF+0x14  u32      1
  GFOF+0x18  f32      0.2
  GFOF+0x1c  u32      8
  GFOF+0x20  u32      8
  GFOF+0x24  u32      ?
  GFOF+0x28..+0x34 zero
  GFOF+0x38  u32      1000
  GFOF+0x3c  u32      0
  GFOF+0x40  f32      1.0
  GFOF+0x44  u32      ?
  GFOF+0x48  glyph record table, glyphCount * 36 bytes
  ...        packed 8-bit glyph bitmap blob

  record (36 bytes):
    +0x00 f32 advance
    +0x04 f32 x0     (left bearing)
    +0x08 f32 y0     (top,  negative = above baseline)
    +0x0c f32 x1     (right)
    +0x10 f32 y1     (bottom)
    +0x14 f32 bmpW
    +0x18 f32 bmpH
    +0x1c u32 bmpOffset  (relative to blob start)
    +0x20 u32 codepoint
"""
import os, sys, struct, json

ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
HDR = 0x48
REC = 36
FMT = "<7f2I"

def parse(path, verbose=True):
    data = open(path, "rb").read()
    g = data.find(b"GFOF")
    if g < 0:
        return None
    n = struct.unpack_from("<I", data, g + 4)[0]
    hdr = struct.unpack_from("<4x I 2f 2I f 3I 7I", data, g) if False else None
    tbl = g + HDR
    end = tbl + n * REC
    recs = []
    for i in range(n):
        o = tbl + i * REC
        if o + REC > len(data):
            break
        adv, x0, y0, x1, y1, w, h, boff, cp = struct.unpack_from(FMT, data, o)
        recs.append(dict(i=i, off=o, adv=adv, x0=x0, y0=y0, x1=x1, y1=y1,
                         w=w, h=h, boff=boff, cp=cp))
    return dict(path=path, data=data, gfof=g, n=n, tbl=tbl, end=end, recs=recs)

def validate(r):
    """Return dict of sanity statistics."""
    data, recs, end = r["data"], r["recs"], r["end"]
    blob = len(data) - end
    ok_cp = ok_wh = ok_box = ok_chain = 0
    bad = []
    prev = None
    maxreach = 0
    for rc in recs:
        cp, w, h, bo = rc["cp"], rc["w"], rc["h"], rc["boff"]
        if 0 <= cp <= 0x10FFFF: ok_cp += 1
        if w == int(w) and h == int(h) and 0 <= w <= 512 and 0 <= h <= 512: ok_wh += 1
        # box vs w/h
        bw, bh = rc["x1"] - rc["x0"], rc["y1"] - rc["y0"]
        if abs(bw - w) <= 2.0 and abs(bh - h) <= 2.0: ok_box += 1
        # chain: bmpOffset[i] + w*h == bmpOffset[i+1]
        if prev is not None:
            if prev[0] + prev[1] * prev[2] == bo: ok_chain += 1
            elif len(bad) < 8: bad.append((rc["i"], prev, bo))
        prev = (bo, int(w), int(h))
        maxreach = max(maxreach, bo + int(w) * int(h))
    return dict(n=len(recs), blob=blob, ok_cp=ok_cp, ok_wh=ok_wh, ok_box=ok_box,
                ok_chain=ok_chain, maxreach=maxreach, bad=bad,
                blob_fit=maxreach - blob)

def main():
    files = sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin"))
    sel = sys.argv[1] if len(sys.argv) > 1 else None
    for fn in files:
        if sel and sel not in fn: continue
        r = parse(os.path.join(ATLAS, fn))
        v = validate(r)
        print(f"{fn}")
        print(f"   GFOF@0x{r['gfof']:x} n={r['n']} tbl=0x{r['tbl']:x} tblEnd=0x{r['end']:x} "
              f"filesize=0x{len(r['data']):x} blob={v['blob']}")
        print(f"   valid cp={v['ok_cp']}/{v['n']}  int wh={v['ok_wh']}/{v['n']}  "
              f"box~wh={v['ok_box']}/{v['n']}  chain={v['ok_chain']}/{v['n']-1}  "
              f"maxreach={v['maxreach']} blob-delta={v['blob_fit']}")
        if v["bad"]:
            print(f"   first chain breaks: {v['bad'][:4]}")
        # codepoint ranges
        cps = [x["cp"] for x in r["recs"]]
        import collections
        buckets = collections.Counter()
        for c in cps:
            if c < 0x80: buckets["ASCII"] += 1
            elif c < 0x250: buckets["Latin-ext"] += 1
            elif 0x370 <= c < 0x400: buckets["Greek"] += 1
            elif 0x400 <= c < 0x500: buckets["Cyrillic"] += 1
            elif 0x590 <= c < 0x600: buckets["HEBREW"] += 1
            elif 0x600 <= c < 0x700: buckets["Arabic"] += 1
            elif 0xFB50 <= c < 0xFE00: buckets["ArabicPresA"] += 1
            elif 0xFE70 <= c < 0xFF00: buckets["ArabicPresB"] += 1
            elif 0x3040 <= c < 0x3100: buckets["Kana"] += 1
            elif 0x4E00 <= c < 0xA000: buckets["CJK"] += 1
            elif 0xAC00 <= c < 0xD7A4: buckets["Hangul"] += 1
            else: buckets["other"] += 1
        print("   scripts:", dict(buckets.most_common()))
        print(f"   sorted-by-cp: {cps == sorted(cps)}   unique: {len(set(cps))}")
        print()

if __name__ == "__main__":
    main()
