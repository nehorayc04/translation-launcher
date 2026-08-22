#!/usr/bin/env python3
"""verify_hebrew_faces.py — parse an FFdec font XML and report, per DefineCompactedFont
face, how many glyphs total + how many Hebrew (glyphCode 1488..1514) + whether the
Hebrew glyph shapes are non-empty (real outlines, not blank)."""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
for it in root.iter("item"):
    if it.get("type") != "DefineCompactedFont":
        continue
    fonts = it.find("fonts")
    if fonts is None:
        continue
    ft = fonts.find("item")
    if ft is None or ft.get("type") != "FontType":
        continue
    fn = ft.get("fontName")
    gi = ft.find("glyphInfo")
    gl = ft.find("glyphs")
    if gi is None:
        continue
    infos = gi.findall("item")
    glyphs = gl.findall("item") if gl is not None else []
    codes = [int(g.get("glyphCode")) for g in infos if g.get("glyphCode")]
    heb_idx = [i for i, c in enumerate(codes) if 1488 <= c <= 1514]
    # check the Hebrew glyph shapes are non-empty (have child shape records)
    nonempty = 0
    for i in heb_idx:
        if i < len(glyphs) and len(list(glyphs[i])) > 0:
            nonempty += 1
    print(f"  face {fn!r}: total={len(codes)} hebrew={len(heb_idx)} hebrew_nonempty_shapes={nonempty} fontId={it.get('fontId')}")
