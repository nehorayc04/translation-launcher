#!/usr/bin/env python3
"""font_transplant.py — graft the WORKING Hebrew font faces from the generic-Hebrew
font into the real PC font, at the FFdec-XML level.

The prior session embedded Hebrew into font_lib_efigs.gfx (generic) with JPEXS FFdec —
it works in-game. Its DefineCompactedFont faces 'Chalet-LondonNineteenSixty' (=$Font2,
the pause-menu text) and the condensed Chalet carry 3461 glyphs incl. the 27 Hebrew
letters (U+05D0..05EA). The real PC font (font_lib_efigs_pc.gfx) has the SAME face names
but only the vanilla Latin glyphs -> pause-menu tofu. We swap the whole <fonts> subtree
(proven Hebrew glyphs) from genHe into the matching PC DefineCompactedFont, KEEPING the
PC font's fontId so the $Font2 export still resolves. FFdec xml2swf rebuilds the binary.

Usage: py -3 font_transplant.py <pc.xml> <genHe.xml> <out_pc_he.xml>
"""
import sys
import xml.etree.ElementTree as ET

# PC face name  ->  generic-Hebrew face name that carries the Hebrew glyphs
FACE_MAP = {
    "Chalet-LondonNineteenSixty": "Chalet-LondonNineteenSixty",          # $Font2 (pause menu)
    "ChaletComprime-CologneSixty": "ChaletComprime CologneSixtyScale",   # $Font2_cond / $Font5
}


def font_name_of(compacted_item):
    """Return the FontType fontName inside a DefineCompactedFont <item>, or None."""
    fonts = compacted_item.find("fonts")
    if fonts is None:
        return None, None
    ft = fonts.find("item")
    if ft is None or ft.get("type") != "FontType":
        return fonts, None
    return fonts, ft.get("fontName")


def main():
    pc_path, gen_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    print("parsing genHe (donor)...")
    gen = ET.parse(gen_path).getroot()
    # map donor fontName -> its <fonts> element
    donor = {}
    for it in gen.iter("item"):
        if it.get("type") == "DefineCompactedFont":
            fonts, fn = font_name_of(it)
            if fn:
                donor[fn] = fonts
    print("  donor faces:", list(donor))

    print("parsing pc (target)...")
    tree = ET.parse(pc_path)
    root = tree.getroot()
    swapped = []
    for it in root.iter("item"):
        if it.get("type") != "DefineCompactedFont":
            continue
        fonts, fn = font_name_of(it)
        if fn in FACE_MAP and FACE_MAP[fn] in donor:
            new_fonts = donor[FACE_MAP[fn]]
            # count glyphs before/after for the log
            old_n = len(it.find("fonts").find("item").find("glyphInfo") or [])
            # replace the <fonts> child: remove old, append a deep copy of donor's
            import copy
            it.remove(it.find("fonts"))
            it.append(copy.deepcopy(new_fonts))
            new_n = len(it.find("fonts").find("item").find("glyphInfo") or [])
            swapped.append((fn, it.get("fontId"), old_n, new_n))

    print("SWAPPED faces (face, fontId, oldGlyphs, newGlyphs):")
    for s in swapped:
        print("  ", s)
    if not swapped:
        sys.exit("!! no faces swapped — name mismatch")
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
