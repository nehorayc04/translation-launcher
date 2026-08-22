# -*- coding: utf-8 -*-
r"""
GFOF - Ubisoft Anvil (forge v50) baked glyph-cache resource, class hash 0xcbd4939a.
FULLY DECODED format.

  <anvil resource header ...>
  GFOF+0x00  char[4]  'GFOF'
  GFOF+0x04  u32      3334          (constant in all 11 resources - cache capacity)
  GFOF+0x08  f32      ascent  factor (1.282 / 1.168 / 1.141)
  GFOF+0x0c  f32      descent factor (0.615 / 0.570 / 0.5586)
  GFOF+0x10  u32      40            (pixel size the cache was baked at)
  GFOF+0x14  u32      1
  GFOF+0x18  f32      0.2
  GFOF+0x1c  u32      8
  GFOF+0x20  u32      8 or 9
  GFOF+0x24  ---- first FACE block starts here ----

  FACE block:
    +0x00  u32   glyphCount
    +0x04  u32[4] 0,0,0,0
    +0x14  u32   1000 (or 1024)
    +0x18  u32   0
    +0x1c  f32   1.0
    +0x20  GLYPH record[glyphCount], 36 bytes each

  GLYPH record (36 bytes), sorted by DESCENDING bitmapH (shelf bin-packer order):
    +0x00  u32   codepoint (UTF-32)
    +0x04  f32   advance
    +0x08  f32   x0     (left,  negative = padding/bearing)
    +0x0c  f32   y0     (top,   negative = above baseline)
    +0x10  f32   x1     (right)
    +0x14  f32   y1     (bottom)
    +0x18  f32   bitmapW (integral)
    +0x1c  f32   bitmapH (integral)
    +0x20  u32   bitmapOffset

  Face blocks are laid back-to-back. After the LAST face block comes one shared
  packed 8-bit-alpha glyph-bitmap blob; bitmapOffset is relative to the GFOF
  magic's own file offset, row stride == bitmapW, no padding between glyphs:
      bitmapOffset[i+1] == bitmapOffset[i] + bitmapW[i]*bitmapH[i]
  (chain is continuous ACROSS face boundaries - one blob for the whole file).
"""
import os, sys, struct, collections

ATLAS = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acblackflag\work\atlas"
REC = 36
RFMT = "<I7fI"        # cp, adv, x0,y0,x1,y1, w,h, boff

def script_of(c):
    if c < 0x80: return "ASCII"
    if c < 0x250: return "Latin-ext"
    if 0x370 <= c < 0x400: return "Greek"
    if 0x400 <= c < 0x530: return "Cyrillic"
    if 0x590 <= c < 0x600: return "HEBREW"
    if 0x600 <= c < 0x700: return "Arabic"
    if 0x750 <= c < 0x780: return "ArabicSuppl"
    if 0xE000 <= c < 0xF900: return "PUA"
    if 0xFB50 <= c < 0xFE00: return "ArabicPresA"
    if 0xFE70 <= c < 0xFF00: return "ArabicPresB"
    if 0x3040 <= c < 0x3100: return "Kana"
    if 0x4E00 <= c < 0xA000: return "CJK"
    if 0xAC00 <= c < 0xD7A4: return "Hangul"
    return "other"

class Gfof:
    def __init__(self, path):
        self.path = path
        self.data = d = open(path, "rb").read()
        self.g = g = d.find(b"GFOF")
        if g < 0: raise ValueError("no GFOF magic")
        self.cap      = struct.unpack_from("<I", d, g + 0x04)[0]
        self.ascent   = struct.unpack_from("<f", d, g + 0x08)[0]
        self.descent  = struct.unpack_from("<f", d, g + 0x0c)[0]
        self.pxsize   = struct.unpack_from("<I", d, g + 0x10)[0]
        self.faces = []
        o = g + 0x24
        while True:
            if o + 0x20 > len(d): break
            n = struct.unpack_from("<I", d, o)[0]
            if n == 0 or n > 20000: break
            rs = o + 0x20
            if rs + n * REC > len(d): break
            recs = [struct.unpack_from(RFMT, d, rs + i * REC) for i in range(n)]
            # validate: every cp sane, w/h integral, chain continuous
            if not all(0 <= r[0] <= 0x10FFFF and r[6] == int(r[6]) and r[7] == int(r[7])
                       and 0 <= r[6] <= 1024 and 0 <= r[7] <= 1024 for r in recs):
                break
            self.faces.append(dict(hdr=o, rec=rs, n=n, recs=recs))
            o = rs + n * REC
        self.blob_base = g          # bitmapOffset is relative to the GFOF magic
        self.meta_end = o

    def all_recs(self):
        for k, f in enumerate(self.faces):
            for r in f["recs"]:
                yield k, r

    def check_chain(self):
        prev = None; breaks = []
        for k, r in self.all_recs():
            cp, adv, x0, y0, x1, y1, w, h, bo = r
            if prev is not None and prev != bo:
                breaks.append((k, cp, prev, bo))
            prev = bo + int(w) * int(h)
        return prev, breaks

    def bitmap(self, r):
        cp, adv, x0, y0, x1, y1, w, h, bo = r
        w, h = int(w), int(h)
        s = self.blob_base + bo
        return self.data[s:s + w * h], w, h

RAMP = " .:-=+*#%@"
def art(px, w, h, maxw=60):
    if w == 0 or h == 0: return "(empty)"
    st = max(1, (w + maxw - 1) // maxw)
    return "\n".join("".join(RAMP[min(9, px[y*w+x]*10//256)] for x in range(0, w, st))
                     for y in range(0, h, st*2))

def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else None
    summary = []
    for fn in sorted(f for f in os.listdir(ATLAS) if f.endswith(".bin")):
        if sel and sel not in fn: continue
        G = Gfof(os.path.join(ATLAS, fn))
        reach, breaks = G.check_chain()
        total = sum(f["n"] for f in G.faces)
        pad = len(G.data) - G.blob_base - reach
        print("=" * 100)
        print(f"{fn}   size={len(G.data)} (0x{len(G.data):x})")
        print(f"  GFOF@0x{G.g:x}  cap={G.cap} pxsize={G.pxsize} asc={G.ascent:.4f} desc={G.descent:.4f}")
        print(f"  faces={len(G.faces)}  glyphs={total}  metaEnd=0x{G.meta_end:x}  "
              f"blobStart=0x{G.blob_base + G.faces[0]['recs'][0][8]:x}  "
              f"blobEnd=0x{G.blob_base+reach:x}  trailingPad={pad}  chainBreaks={len(breaks)}")
        for k, f in enumerate(G.faces):
            b = collections.Counter(script_of(r[0]) for r in f["recs"])
            hs = [int(r[7]) for r in f["recs"]]
            print(f"    face{k}: hdr@0x{f['hdr']:06x} rec@0x{f['rec']:06x} n={f['n']:<5} "
                  f"h:{max(hs)}->{min(hs)}  {dict(b.most_common(6))}")
        summary.append((fn, total, len(G.data), G.faces))
        print()

    if len(summary) > 1:
        print("=" * 100)
        print("size vs glyph-count correlation (task 6):")
        print(f"{'file':26s} {'glyphs':>7} {'size':>10} {'bytes/glyph':>12} {'sum w*h':>12}")
        for fn, total, sz, faces in summary:
            px = sum(int(r[6]) * int(r[7]) for f in faces for r in f["recs"])
            print(f"{fn:26s} {total:>7} {sz:>10} {sz/total:>12.1f} {px:>12}")

if __name__ == "__main__":
    main()
