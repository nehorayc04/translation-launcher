#!/usr/bin/env python3
"""fОnk research: dump exe string context around font structs, map ASCII string
clusters, and detect any RTTI/typeinfo layout hints. Read-only against the real exe."""
import re, sys, os

EXE = r"F:/Games/Ghost of Tsushima DC/GhostOfTsushima.exe"

def load(p):
    with open(p, "rb") as f:
        return f.read()

def ascii_strings(buf, minlen=4):
    """Yield (offset, string) for printable ASCII runs."""
    out = []
    cur = bytearray(); start = 0
    for i, b in enumerate(buf):
        if 0x20 <= b < 0x7f:
            if not cur:
                start = i
            cur.append(b)
        else:
            if len(cur) >= minlen:
                out.append((start, cur.decode("ascii")))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append((start, cur.decode("ascii")))
    return out

def main():
    buf = load(EXE)
    print(f"exe size = {len(buf):,}")
    strs = ascii_strings(buf, 4)
    print(f"ascii strings (>=4) = {len(strs):,}")

    # Terms of interest
    terms = ["SFontData","FontGlyphs","FontVerts","FONTK","FONT_KIND","FONT_SIZE",
             "fOnk","Font","Glyph","CreateFontW","AddFontMemResourceEx",
             "RemoveFontMemResourceEx","Launcher_Font","LARGE_FONT",
             "kerning","Kerning","advance","Advance","baseline","ascent","descent",
             "SFont","GlyphVert","GlyphIndex","codepoint","CodePoint","texmesh",
             "sprig","packman","KCAP","fOnk","NAMS"]

    # index strings by offset for neighbor lookup
    by_off = {off:(off,s) for off,s in strs}
    offs_sorted = sorted(by_off)

    print("\n=== exact/substr hits for font-struct terms ===")
    seen = {}
    for off, s in strs:
        for t in ["SFontData","FontGlyphs","FontVerts","FONTK","FONT_KIND",
                  "FONT_SIZE","LARGE_FONT","Launcher_Font"]:
            if t in s:
                seen.setdefault(t, []).append((off, s))
    for t in sorted(seen):
        print(f"\n-- {t}  ({len(seen[t])} hits) --")
        for off, s in seen[t][:8]:
            print(f"  0x{off:08x}: {s!r}")

    # Cluster: print a window of strings physically around the first SFontData / FontGlyphs / FontVerts
    print("\n=== neighborhood clusters (physically adjacent ascii strings) ===")
    import bisect
    for anchor in ["SFontData","FontGlyphs","FontVerts","FONT_KIND","FONT_SIZE"]:
        hits = [o for o,s in strs if anchor in s]
        if not hits:
            print(f"\n[{anchor}] NOT FOUND as ascii string")
            continue
        a = hits[0]
        i = bisect.bisect_left(offs_sorted, a)
        lo = max(0, i-12); hi = min(len(offs_sorted), i+13)
        print(f"\n[{anchor}] around 0x{a:08x}:")
        for j in range(lo, hi):
            o = offs_sorted[j]
            mark = " <==" if o == a else ""
            print(f"   0x{o:08x}: {by_off[o][1]!r}{mark}")

    # Look for all strings containing 'font' case-insensitive
    print("\n=== all strings containing 'font' (case-insensitive), first 60 ===")
    fonts = [(o,s) for o,s in strs if "font" in s.lower()]
    print(f"total = {len(fonts)}")
    for o,s in fonts[:60]:
        print(f"  0x{o:08x}: {s!r}")

if __name__ == "__main__":
    main()
