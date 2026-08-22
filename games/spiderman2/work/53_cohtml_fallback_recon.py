"""How does cohtml resolve glyphs the UI font (AzbukaPro) lacks?

Search the cohtml + Renoir DLLs for the font-fallback machinery: DirectWrite
usage, system-font fallback APIs, hard-coded fallback font names, and any
per-script config. The goal is to learn whether Arabic is rendered from a
BUNDLED font asset (which we could swap) or via the OS (DirectWrite system
fallback) — which would explain why Arabic works but Hebrew is tofu.
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")

DLLS = ["cohtml.WindowsDesktop.dll", "RenoirCore.WindowsDesktop.dll",
        "cohtml_icuuc.dll"]

# Token groups we care about
GROUPS = {
    "DirectWrite / OS font system": [
        b"DirectWrite", b"DWrite", b"IDWriteFontFallback", b"IDWriteFactory",
        b"GetSystemFontFallback", b"CreateFontFallback", b"MapCharacters",
        b"AddFontMemResourceEx", b"CreateFontFace", b"GetSystemFontCollection",
    ],
    "cohtml fallback API / config": [
        b"FontFallback", b"fallback", b"Fallback", b"SetDefaultBackendFont",
        b"SystemFontDescription", b"SetSystemFontDescription",
        b"DefaultFontFamily", b"m_FallbackFonts", b"FontFaceCollection",
        b"backend_font", b"cohtml", b"coui",
    ],
    "candidate fallback font names": [
        b"Tahoma", b"Segoe", b"Arial", b"Microsoft Sans", b"MS Shell",
        b"Noto", b"NotoSans", b"Helvetica", b"sans-serif", b"DejaVu",
        b"Yu Gothic", b"Malgun", b"SimSun", b"Meiryo", b"Gulim",
        b"Geeza", b"Sakkal", b"Aldhabi", b"Simplified Arabic", b"Traditional Arabic",
        b"AzbukaPro", b"David", b"FrankRuehl", b"Gisha", b"Rod ", b"Levenim",
    ],
    "script names / unicode hints": [
        b"hebrew", b"Hebrew", b"arabic", b"Arabic", b"latin", b"Latin",
        b"Hebr", b"Arab", b"he-IL", b"ar-SA", b"ScriptAnalysis",
    ],
    "embedded font / file refs": [
        b".ttf", b".otf", b".ttc", b".woff", b"font/", b"fonts/",
        b"OTTO", b"sfnt",
    ],
}


def context(buf, j, span=48):
    s = buf[max(0, j-8):j+span]
    return "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in s)


for dll in DLLS:
    path = os.path.join(GAME, dll)
    if not os.path.exists(path):
        print(f"[!] missing {dll}")
        continue
    buf = open(path, "rb").read()
    print("\n" + "=" * 72)
    print(f"{dll}  ({len(buf):,} bytes)")
    print("=" * 72)
    for group, tokens in GROUPS.items():
        hits = []
        for t in tokens:
            c = buf.count(t)
            if c:
                j = buf.find(t)
                hits.append((t, c, j))
        if hits:
            print(f"\n  [{group}]")
            for t, c, j in sorted(hits, key=lambda x: -x[1]):
                print(f"    {t.decode('latin-1'):<26} x{c:<4} first@{j:<9} | {context(buf, j)!r}")
