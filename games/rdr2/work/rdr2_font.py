#!/usr/bin/env python3
"""rdr2_font.py — inject the 27 Hebrew letters (U+05D0..05EA) into EVERY DefineCompactedFont
face of RDR2's Scaleform `font_lib_efigs.gfx`, at the FFdec-XML level.

RDR2 (RAGE) uses the SAME Scaleform DefineCompactedFont font family as GTA V, so the proven
GTA V technique applies unchanged: decompile the .gfx to XML with FFdec, add the 27 Hebrew
glyph outlines (lifted from the GTA V Hebrew donor) to every face keeping glyphInfo/glyphs in
ascending glyphCode order, recompile with FFdec (which recomputes globalOffsets). Ko Games'
shipping RDR2 Arabic mod proves glyph injection into THIS exact .gfx renders in-game; here we
add Hebrew instead of Arabic. Hebrew needs no shaping, so 27 base letters suffice.

Pipeline:
  java -jar ffdec.jar -swf2xml font_lib_efigs.gfx  rdr2_font.xml
  python rdr2_font.py <donor_gen_allheb.xml> rdr2_font.xml rdr2_font_he.xml
  java -jar ffdec.jar -xml2swf rdr2_font_he.xml    font_lib_efigs.gfx   # the Hebrew font

Reuses the audited add_to_face / template logic from ../../gtav/work/font_add_hebrew.py; only
the donor-face selection is auto-detected (the GTA donor's face names differ per build).
"""
import copy
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "gtav", "work")))
from font_add_hebrew import font_type, add_to_face, HEB_LO, HEB_HI  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def collect_hebrew_templates_any(donor_root):
    """Lift 27 self-contained Hebrew glyph templates from ANY donor face that has the full
    U+05D0..05EA set (the GTA donor's face names vary; auto-detect instead of hardcoding)."""
    best = None
    for it in donor_root.iter("item"):
        if it.get("type") != "DefineCompactedFont":
            continue
        ft = font_type(it)
        if ft is None:
            continue
        gi = ft.find("glyphInfo").findall("item")
        gl = ft.find("glyphs").findall("item")
        out = []
        for i, g in enumerate(gi):
            c = int(g.get("glyphCode"))
            if HEB_LO <= c <= HEB_HI:
                ref = any(ct.get("isReference") == "true"
                          for ct in gl[i].iter("item") if ct.get("type") == "ContourType")
                if ref:
                    out = []
                    break
                out.append((c, copy.deepcopy(g), copy.deepcopy(gl[i])))
        out.sort(key=lambda t: t[0])
        if len(out) == (HEB_HI - HEB_LO + 1):
            print(f"donor face '{ft.get('fontName')}' -> {len(out)} self-contained Hebrew glyphs")
            return out
    raise SystemExit("!! no donor face has a full self-contained 27-glyph Hebrew set")


def main():
    donor_path, target_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    print("parsing donor ...")
    templates = collect_hebrew_templates_any(ET.parse(donor_path).getroot())
    print("parsing target (large) ...")
    tree = ET.parse(target_path)
    root = tree.getroot()
    n = 0
    for it in root.iter("item"):
        if it.get("type") != "DefineCompactedFont":
            continue
        ft = font_type(it)
        if ft is None:
            continue
        total = add_to_face(ft, templates)
        n += 1
        print(f"  +27 Hebrew -> {ft.get('fontName')!r:36} (now {total} glyphs)")
    print(f"updated {n} faces; writing ...")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
