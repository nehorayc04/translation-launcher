#!/usr/bin/env python3
"""font_add_hebrew.py — SURGICALLY add the 27 Hebrew letters (U+05D0..05EA) into EVERY
DefineCompactedFont face of a GTA V font .gfx, at the FFdec-XML level.

Why this and not the old whole-face transplant: in-game evidence showed the PC font LOADS
(Latin tabs render crisp) but Hebrew title/player text is tofu -> the Hebrew elements use a
face that had NO Hebrew. The old transplant only put Hebrew into 2 Chalet faces. This adds
the 27 Hebrew glyphs to ALL faces, so whichever face an element uses, the glyph exists.

The Hebrew glyph templates (GlyphInfoType + GlyphType, self-contained outlines with matching
~EM) are lifted from the proven generic-Hebrew donor's Chalet-LondonNineteenSixty face. They
are inserted (parallel glyphInfo+glyphs arrays kept in sorted glyphCode order); FFdec
recomputes every globalOffset on xml2swf (verified), so no manual offset math is needed.

Usage: py -3 font_add_hebrew.py <donor_hebrew.xml> <target_vanilla.xml> <out.xml>
"""
import sys, copy
import xml.etree.ElementTree as ET

HEB_LO, HEB_HI = 0x5D0, 0x5EA          # 1488..1514 (alef..tav)
DONOR_FACE = "Chalet-LondonNineteenSixty"


def font_type(item):
    f = item.find("fonts")
    if f is None:
        return None
    ft = f.find("item")
    return ft if (ft is not None and ft.get("type") == "FontType") else None


def collect_hebrew_templates(donor_root):
    """-> ordered list of (code, glyphInfoElem, glyphElem) for codes HEB_LO..HEB_HI."""
    for it in donor_root.iter("item"):
        if it.get("type") != "DefineCompactedFont":
            continue
        ft = font_type(it)
        if ft is None or ft.get("fontName") != DONOR_FACE:
            continue
        gi = ft.find("glyphInfo").findall("item")
        gl = ft.find("glyphs").findall("item")
        out = []
        for i, g in enumerate(gi):
            c = int(g.get("glyphCode"))
            if HEB_LO <= c <= HEB_HI:
                # safety: a self-contained outline (no cross-glyph reference)
                for ct in gl[i].iter("item"):
                    if ct.get("type") == "ContourType" and ct.get("isReference") == "true":
                        raise SystemExit(f"!! Hebrew glyph {c} uses a contour reference — unsafe to port")
                out.append((c, copy.deepcopy(g), copy.deepcopy(gl[i])))
        out.sort(key=lambda t: t[0])
        if len(out) != (HEB_HI - HEB_LO + 1):
            raise SystemExit(f"!! donor has {len(out)} Hebrew glyphs, expected 27")
        return out
    raise SystemExit("!! donor face not found")


def add_to_face(ft, templates):
    gi_parent = ft.find("glyphInfo")
    gl_parent = ft.find("glyphs")
    gi = gi_parent.findall("item")
    gl = gl_parent.findall("item")
    # build parallel (code, giElem, glElem), drop any pre-existing Hebrew
    pairs = []
    for a, b in zip(gi, gl):
        c = int(a.get("glyphCode"))
        if HEB_LO <= c <= HEB_HI:
            continue
        pairs.append((c, a, b))
    for c, giE, glE in templates:
        pairs.append((c, copy.deepcopy(giE), copy.deepcopy(glE)))
    pairs.sort(key=lambda t: t[0])
    # rewrite both containers in the new sorted order
    for parent in (gi_parent, gl_parent):
        for ch in list(parent):
            parent.remove(ch)
    for c, giE, glE in pairs:
        gi_parent.append(giE)
        gl_parent.append(glE)
    return len(pairs)


def main():
    donor_path, target_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    templates = collect_hebrew_templates(ET.parse(donor_path).getroot())
    print(f"donor Hebrew templates: {len(templates)} (codes {templates[0][0]}..{templates[-1][0]})")
    tree = ET.parse(target_path)
    root = tree.getroot()
    n_faces = 0
    for it in root.iter("item"):
        if it.get("type") != "DefineCompactedFont":
            continue
        ft = font_type(it)
        if ft is None:
            continue
        total = add_to_face(ft, templates)
        n_faces += 1
        print(f"  face {ft.get('fontName')!r:36} fontId={it.get('fontId')} -> {total} glyphs (+27 Hebrew)")
    print(f"updated {n_faces} faces")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
