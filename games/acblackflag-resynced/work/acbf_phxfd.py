#!/usr/bin/env python3
"""acbf_phxfd.py -- parse the AC Black Flag Resynced (v50) PhoenixFontDescriptorData
baked glyph atlas (class hash 0xCBD4939A), using the AC Shadows (v42) PHXFD model.

Model (from games/acshadows/work/acs_atlas_inject.py, proven on v42):
    ... wrapper ... "PHXFD" + opaque const header + "GFOF" section
    GFOF+36 : u32 glyphCount
    GFOF+72 : glyphCount x 36-byte record:
        f32[7] = advance, xMin, yMin, xMax, yMax, W, H     (px bbox)
        u32    tex_offset   (ABSOLUTE offset into the decoded object)
        u32    codepoint
    raster  = dec[tex_offset : tex_offset + W*H]  8-bit SDF, edge ~128, row-major
"""
import os, sys, struct, collections

ATLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas")
FILES = ["16243_88c2952a.bin", "16245_88c2952b.bin", "16248_88c2952c.bin",
         "19498_88cf5a5b.bin", "19499_8b21454b.bin", "19500_88cf5a5c.bin",
         "70970_88c902b3.bin", "70971_88c902b5.bin", "70972_88c902b1.bin",
         "70973_88cab006.bin", "70974_88c902b0.bin"]


def load(n):
    with open(os.path.join(ATLAS, n), "rb") as f:
        return f.read()


def parse(dec):
    p = dec.find(b"PHXFD")
    g = dec.find(b"GFOF")
    if g < 0:
        raise ValueError("no GFOF")
    hdr = dict(phxfd=p, gfof=g)
    hdr["h4"] = struct.unpack_from("<I", dec, g + 4)[0]
    hdr["f8"] = struct.unpack_from("<f", dec, g + 8)[0]
    hdr["f12"] = struct.unpack_from("<f", dec, g + 12)[0]
    hdr["u16"] = struct.unpack_from("<I", dec, g + 16)[0]
    hdr["u20"] = struct.unpack_from("<I", dec, g + 20)[0]
    hdr["f24"] = struct.unpack_from("<f", dec, g + 24)[0]
    hdr["u28"] = struct.unpack_from("<I", dec, g + 28)[0]
    hdr["u32_"] = struct.unpack_from("<I", dec, g + 32)[0]
    cnt = struct.unpack_from("<I", dec, g + 36)[0]
    hdr["count"] = cnt
    hdr["rest"] = struct.unpack_from("<8I", dec, g + 40)
    start = g + 72
    recs = []
    for k in range(cnt):
        o = start + 36 * k
        m = struct.unpack_from("<7f", dec, o)
        tex, cp = struct.unpack_from("<II", dec, o + 28)
        recs.append(dict(i=k, adv=m[0], xmin=m[1], ymin=m[2], xmax=m[3], ymax=m[4],
                         w=m[5], h=m[6], tex=tex, cp=cp, o=o))
    hdr["rec_start"] = start
    hdr["rec_end"] = start + 36 * cnt
    return hdr, recs


BLOCKS = [
    ("Latin/ASCII", 0x20, 0x7F), ("Latin-1", 0x80, 0xFF), ("LatinExtA", 0x100, 0x17F),
    ("LatinExtB", 0x180, 0x24F), ("Greek", 0x370, 0x3FF), ("Cyrillic", 0x400, 0x4FF),
    ("HEBREW", 0x590, 0x5FF), ("Arabic", 0x600, 0x6FF), ("ArabicSupp", 0x750, 0x77F),
    ("ArabicExtA", 0x8A0, 0x8FF), ("Punct", 0x2000, 0x206F), ("CJK", 0x4E00, 0x9FFF),
    ("Hangul", 0xAC00, 0xD7AF), ("ArabicPresA", 0xFB50, 0xFDFF),
    ("ArabicPresB", 0xFE70, 0xFEFF), ("Hiragana", 0x3040, 0x30FF),
]


def blockname(cp):
    for n, a, b in BLOCKS:
        if a <= cp <= b:
            return n
    return f"other<0x{cp:04X}>"


def cmd_parse():
    for n in FILES:
        d = load(n)
        try:
            hdr, recs = parse(d)
        except Exception as e:
            print(f"{n}: FAIL {e}")
            continue
        cps = [r["cp"] for r in recs]
        blocks = collections.Counter(blockname(c) for c in cps)
        # size identity: does tex_offset + W*H stay inside the file and tile it?
        ends = [r["tex"] + int(round(r["w"])) * int(round(r["h"])) for r in recs]
        rasterbase = min(r["tex"] for r in recs)
        rastermax = max(ends)
        exact = sum(1 for r, e in zip(recs, ends) if 0 < r["tex"] < len(d) and e <= len(d))
        total_px = sum(int(round(r["w"])) * int(round(r["h"])) for r in recs)
        print(f"\n=== {n}  ({len(d):,} B) ===")
        print(f"  PHXFD@0x{hdr['phxfd']:x}  GFOF@0x{hdr['gfof']:x}  glyphCount={hdr['count']}")
        print(f"  GFOF hdr: h4={hdr['h4']} sdfA={hdr['f8']:.4f} sdfB={hdr['f12']:.4f} "
              f"u16={hdr['u16']} u20={hdr['u20']} f24={hdr['f24']:.4f} pad={hdr['u28']} u32={hdr['u32_']}")
        print(f"  records 0x{hdr['rec_start']:x}..0x{hdr['rec_end']:x}  ({36*hdr['count']:,} B)")
        print(f"  tex range: 0x{rasterbase:x}..0x{rastermax:x}   file end 0x{len(d):x}   "
              f"slack={len(d)-rastermax}")
        print(f"  sum(W*H) = {total_px:,}   raster span = {rastermax-rasterbase:,}  "
              f"in-bounds records = {exact}/{len(recs)}")
        print("  codepoint blocks: " + ", ".join(f"{k}={v}" for k, v in blocks.most_common()))
        heb = [r for r in recs if 0x590 <= r["cp"] <= 0x5FF]
        print(f"  HEBREW records: {len(heb)}" + (" -> " + ",".join(f"U+{r['cp']:04X}" for r in heb[:30]) if heb else ""))


def cmd_verify(name=None):
    """Prove the record table tiles the raster region contiguously."""
    n = name or "70970_88c902b3.bin"
    d = load(n)
    hdr, recs = parse(d)
    srt = sorted(recs, key=lambda r: r["tex"])
    print(f"{n}: {hdr['count']} glyphs, raster tiling check (sorted by tex_offset)")
    gaps = collections.Counter()
    bad = 0
    for a, b in zip(srt, srt[1:]):
        need = int(round(a["w"])) * int(round(a["h"]))
        gap = b["tex"] - (a["tex"] + need)
        gaps[gap] += 1
        if gap < 0:
            bad += 1
    print(f"  gap histogram (next.tex - (this.tex + W*H)) top 12: {gaps.most_common(12)}")
    print(f"  OVERLAPS (negative gap): {bad}")
    last = srt[-1]
    end = last["tex"] + int(round(last["w"])) * int(round(last["h"]))
    print(f"  last glyph U+{last['cp']:04X} tex=0x{last['tex']:x} W={last['w']:.1f} H={last['h']:.1f} "
          f"end=0x{end:x}  filelen=0x{len(d):x}  tail={len(d)-end} B")
    print(f"  first glyph tex=0x{srt[0]['tex']:x}, record table ends 0x{hdr['rec_end']:x}, "
          f"gap between = {srt[0]['tex']-hdr['rec_end']} B")
    print("\n  sample records (first 12 by index):")
    for r in recs[:12]:
        print(f"    #{r['i']:4d} U+{r['cp']:04X} {blockname(r['cp']):12s} adv={r['adv']:7.2f} "
              f"bbox=({r['xmin']:6.2f},{r['ymin']:6.2f})-({r['xmax']:6.2f},{r['ymax']:6.2f}) "
              f"W={r['w']:5.1f} H={r['h']:5.1f} tex=0x{r['tex']:x}")


def cmd_ascii(name="70970_88c902b3.bin", cp=None):
    """ASCII-art a glyph's raster to prove the raster decode."""
    d = load(name)
    hdr, recs = parse(d)
    targets = []
    if cp:
        targets = [r for r in recs if r["cp"] == int(cp, 0)]
    if not targets:
        # pick 'A', an Arabic letter, and the largest glyph
        for want in (0x41, 0x48, 0x627, 0x645):
            targets += [r for r in recs if r["cp"] == want][:1]
    ramp = " .:-=+*#%@"
    for r in targets:
        w, h = int(round(r["w"])), int(round(r["h"]))
        if w <= 0 or h <= 0 or w > 200 or h > 200:
            print(f"U+{r['cp']:04X}: W={w} H={h} (skip)"); continue
        buf = d[r["tex"]:r["tex"] + w * h]
        print(f"\nU+{r['cp']:04X}  W={w} H={h}  tex=0x{r['tex']:x}  bytes={len(buf)}  "
              f"min={min(buf)} max={max(buf)}")
        for y in range(h):
            row = buf[y * w:(y + 1) * w]
            print("   " + "".join(ramp[min(9, b * 10 // 256)] for b in row))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "parse"
    if cmd == "parse":
        cmd_parse()
    elif cmd == "verify":
        cmd_verify(*sys.argv[2:])
    elif cmd == "ascii":
        cmd_ascii(*sys.argv[2:])
