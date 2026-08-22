#!/usr/bin/env python3
"""Investigate the CHEAP-WIN font-fallback question for Ghost of Tsushima.

Question: can we make the engine render Hebrew from an OS/system/external font
instead of cracking the proprietary `fOnk` vector font?

We answer by mining GhostOfTsushima.exe for the font-related API imports + string
context, and clustering the launcher (GDI) path vs the in-game (fOnk vector) path.

READ-ONLY. Verifies against the real exe. Prints concrete offsets + counts.
"""
import re, sys, struct, collections

EXE = r"F:/Games/Ghost of Tsushima DC/GhostOfTsushima.exe"

def load(path):
    with open(path, "rb") as f:
        return f.read()

def ascii_strings(buf, minlen=4):
    """Yield (offset, str) for printable ASCII runs."""
    out = []
    cur = bytearray()
    start = 0
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

def find_all(buf, needle):
    out = []
    i = buf.find(needle)
    while i != -1:
        out.append(i)
        i = buf.find(needle, i + 1)
    return out

def main():
    buf = load(EXE)
    print(f"EXE size = {len(buf):,} bytes")

    # --- 1. Which font-related API imports / strings are present, and where ---
    targets = [
        b"CreateFontW", b"CreateFontA", b"CreateFontIndirectW", b"CreateFontIndirectExW",
        b"AddFontMemResourceEx", b"RemoveFontMemResourceEx",
        b"AddFontResourceW", b"AddFontResourceExW",
        b"GetGlyphOutlineW", b"GetGlyphOutlineA", b"GetGlyphIndicesW",
        b"GetCharABCWidthsW", b"GetTextExtentPoint32W",
        b"SelectObject", b"GetDC", b"CreateCompatibleDC",
        b"EnumFontFamiliesExW", b"GetFontData",
        b"Launcher_Font", b"Launcher_Font_Version",
        b"FontGlyphs", b"FontVerts", b"SFontData", b"FONTK", b"fOnk",
        b"FONT_KIND", b"FONT_SIZE", b"LARGE_FONT_SIZE_FACTOR",
        b"DirectWrite", b"dwrite", b"DWrite", b"IDWriteFactory",
        b"font_link", b"FontLink", b"fallback", b"Fallback", b"SystemFallback",
        b"gdi32", b"GDI32", b"usp10", b"Uniscribe",
    ]
    print("\n=== 1. font-API / font-string presence (offset of first hit + count) ===")
    presence = {}
    for t in targets:
        hits = find_all(buf, t)
        presence[t.decode()] = hits
        if hits:
            print(f"  {t.decode():28s} count={len(hits):3d}  first@0x{hits[0]:X}")
        else:
            print(f"  {t.decode():28s} ABSENT")

    # Also check UTF-16LE for the wide strings (font names / config keys often UTF-16)
    print("\n=== 1b. UTF-16LE presence for key names ===")
    for t in [b"CreateFontW", b"AddFontMemResourceEx", b"Launcher_Font", b"fOnk",
              b"Hebrew", b"hebrew", b"Arabic", b"arabic", b"Segoe", b"Arial", b".ttf", b".otf"]:
        w = t.decode().encode("utf-16le")
        hits = find_all(buf, w)
        if hits:
            print(f"  u16 {t.decode():22s} count={len(hits):3d} first@0x{hits[0]:X}")

    # --- 2. context window around the launcher-font APIs ---
    print("\n=== 2. ASCII neighbourhood around Launcher_Font / AddFontMemResourceEx ===")
    for key in (b"Launcher_Font", b"AddFontMemResourceEx", b"CreateFontW", b"fOnk"):
        hits = presence.get(key.decode(), [])
        if not hits:
            continue
        off = hits[0]
        lo, hi = max(0, off - 400), min(len(buf), off + 400)
        window = buf[lo:hi]
        near = ascii_strings(window, 4)
        toks = [s for (_, s) in near]
        print(f"\n  --- around {key.decode()} @0x{off:X} ---")
        print("   " + " | ".join(toks[:40]))

    # --- 3. list ALL strings that look like a .ttf / .otf / font-file / font-name ref ---
    print("\n=== 3. any font-FILE / font-NAME references (ascii) ===")
    strs = ascii_strings(buf, 4)
    pat = re.compile(r"(\.ttf|\.otf|\.ttc|\.fnt|\.woff|Segoe|Arial|Tahoma|Verdana|Calibri|"
                     r"NotoSans|SourceHan|font\.|Font\.|/fonts?/|\\fonts?\\|Launcher_Font|"
                     r"[Ff]allback|[Ff]ontLink|[Hh]ebrew)", re.I)
    seen = set()
    hits3 = []
    for off, s in strs:
        if pat.search(s) and s not in seen:
            seen.add(s)
            hits3.append((off, s))
    for off, s in hits3[:120]:
        print(f"  0x{off:08X}  {s!r}")
    print(f"  (total distinct = {len(hits3)})")

    # --- 4. cluster: are Launcher_Font + AddFontMemResourceEx near each other and
    #        FAR from fOnk / FontVerts (i.e. two distinct subsystems)? ---
    print("\n=== 4. subsystem clustering (byte distance) ===")
    def firsthit(name):
        h = presence.get(name, [])
        return h[0] if h else None
    anchors = {n: firsthit(n) for n in
               ["Launcher_Font", "AddFontMemResourceEx", "CreateFontW",
                "RemoveFontMemResourceEx", "FontVerts", "FontGlyphs", "SFontData",
                "FONTK", "fOnk", "FONT_KIND"]}
    for n, o in anchors.items():
        print(f"  {n:24s} -> {'0x%X'%o if o is not None else 'ABSENT'}")

if __name__ == "__main__":
    main()
