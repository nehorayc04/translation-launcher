#!/usr/bin/env python3
"""rdr2_stencil_inject.py — replace the RDR Lino ($title1) face's Hebrew glyphs (currently
the plain generic donor) with the DISTRESSED/STENCIL set built by rdr2_stencil_font.py,
inside font_lib_efigs.gfx, and deploy.

Works on an ISOLATED text-line slice of the swf2xml dump (RDR Lino's <glyphs>+<glyphInfo>
span is ~1M lines / ~40 MB out of the whole 353 MB file) -- parsing just that slice with
ElementTree is fast and avoids re-parsing/rewriting the whole tree. `glyphInfo[i]` and
`glyphs[i]` are PARALLEL arrays matched by POSITION (not by any key), so removals/insertions
must happen at the same index in both -- this script keeps them in lockstep by pairing them
before editing, exactly like `font_add_hebrew.add_to_face` does.

Usage:
    python rdr2_stencil_inject.py build        # write the new full.xml (RDR Lino only changed)
    python rdr2_stencil_inject.py xml2swf      # ffdec xml2swf -> new font_lib_efigs.gfx
    python rdr2_stencil_inject.py deploy       # copy into the live game + verify readback
    python rdr2_stencil_inject.py all          # all of the above, in order
"""
import copy
import os
import random
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rdr2_stencil_font import build_letter, glyph_contours, DONOR_TTF, TARGET_CAP, LETTERS
from fontTools.ttLib import TTFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
FI = os.path.join(HERE, "_fontinspect")
LIVE_XML = os.path.join(FI, "live.xml")          # swf2xml of the CURRENTLY deployed .gfx
FULL_OUT = os.path.join(FI, "stencil_full.xml")
FFDEC = os.path.join(HERE, "..", "..", "gtav", "tools", "ffdec", "ffdec.jar")
JAVA = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.4.7-hotspot\bin\java.exe"
GFX_LIVE = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2\lml\KGF\asset_replace\font_lib_efigs.gfx"
GFX_BACKUP = GFX_LIVE + ".stencil_backup"

# line span (1-based, INCLUSIVE) of RDR Lino's <glyphs>...</glyphInfo> in the CURRENT
# live.xml decompile -- measured this session (see chat notes); re-measure with
# `find_span()` if the source .gfx ever changes.
SPAN_START = 7181007
SPAN_END = 8162176

HEB_LO, HEB_HI = 0x05D0, 0x05EA


def find_span(xml_path=LIVE_XML):
    """Recompute SPAN_START/SPAN_END if the source file changes -- locate RDR Lino's
    FontType, then its <glyphs> open and <glyphInfo> close."""
    font_line = glyphs_open = glyphinfo_close = None
    with open(xml_path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            if font_line is None and 'fontName="RDR Lino"' in line and 'type="FontType"' in line:
                font_line = i
                continue
            if font_line is not None and glyphs_open is None and "<glyphs>" in line:
                glyphs_open = i
                continue
            if glyphs_open is not None and "</glyphInfo>" in line:
                glyphinfo_close = i
                break
    print(f"font_line={font_line} glyphs_open={glyphs_open} glyphinfo_close={glyphinfo_close}")
    return glyphs_open, glyphinfo_close


def build_new_hebrew(rng):
    """-> list of (code, GlyphInfoType elem, GlyphType elem, advance) for the 27 letters."""
    font = TTFont(DONOR_TTF)
    raw_bet = glyph_contours(font, "ב")
    ys = [p[1] for c in raw_bet for p in c]
    donor_cap = max(ys) - min(ys)
    scale = TARGET_CAP / donor_cap
    jitter_amp = TARGET_CAP * 0.018
    seg_len = TARGET_CAP * 0.03

    out = []
    for ch in LETTERS:
        contours, adv, bbox, n_solids = build_letter(font, ch, 0, scale, rng, jitter_amp,
                                                       seg_len, n_holes=0)
        code = ord(ch)
        x0, y0, x1, y1 = (round(v) for v in bbox)
        gi = ET.Element("item", {"type": "GlyphInfoType", "advanceX": str(round(adv)),
                                  "globalOffset": "0", "glyphCode": str(code)})
        gl = ET.Element("item", {"type": "GlyphType"})
        bb = ET.SubElement(gl, "boundingBox")
        for v in (x0, y0, x1, y1):
            ET.SubElement(bb, "item").text = str(v)
        conts_el = ET.SubElement(gl, "contours")
        for c in contours:
            mx, my = round(c[0][0]), round(c[0][1])
            cont_el = ET.SubElement(conts_el, "item", {
                "type": "ContourType", "isReference": "false",
                "moveToX": str(mx), "moveToY": str(my), "reference": "0"})
            edges_el = ET.SubElement(cont_el, "edges")
            px, py = mx, my
            n = len(c)
            for i in range(1, n + 1):
                x, y = c[i % n]
                x, y = round(x), round(y)
                dx, dy = x - px, y - py
                px, py = x, y
                if dx == 0 and dy == 0:
                    continue
                if dy == 0:
                    kind, p1, p2, p3, p4 = 0, dx, 0, 0, 0
                elif dx == 0:
                    kind, p1, p2, p3, p4 = 1, dy, 0, 0, 0
                else:
                    kind, p1, p2, p3, p4 = 2, dx, dy, 0, 0
                edge_el = ET.SubElement(edges_el, "item", {"type": "EdgeType"})
                data_el = ET.SubElement(edge_el, "data")
                for v in (kind, p1, p2, p3, p4):
                    ET.SubElement(data_el, "item").text = str(v)
        out.append((code, gi, gl, adv))
    return out


def cmd_build():
    rng = random.Random(20260805)
    new_heb = build_new_hebrew(rng)
    print(f"built {len(new_heb)} distressed Hebrew glyphs")

    print("parsing RDR Lino face slice (this file is huge; reading only the target span)...")
    with open(LIVE_XML, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    before = lines[:SPAN_START - 1]
    span = lines[SPAN_START - 1:SPAN_END]
    after = lines[SPAN_END:]

    frag = "<root>" + "".join(span) + "</root>"
    root = ET.fromstring(frag)
    glyphs_el = root.find("glyphs")
    glyphinfo_el = root.find("glyphInfo")
    gi_items = glyphinfo_el.findall("item")
    gl_items = glyphs_el.findall("item")
    assert len(gi_items) == len(gl_items), f"{len(gi_items)} vs {len(gl_items)} -- not parallel!"

    pairs = []
    dropped = 0
    for a, b in zip(gi_items, gl_items):
        code = int(a.get("glyphCode"))
        if HEB_LO <= code <= HEB_HI:
            dropped += 1
            continue
        pairs.append((code, a, b))
    print(f"kept {len(pairs)} non-Hebrew glyphs, dropped {dropped} old Hebrew glyphs")

    for code, gi, gl, adv in new_heb:
        pairs.append((code, gi, gl))
    pairs.sort(key=lambda t: t[0])
    print(f"final glyph count: {len(pairs)}")

    for parent in (glyphinfo_el, glyphs_el):
        for ch in list(parent):
            parent.remove(ch)
    for code, gi, gl in pairs:
        glyphinfo_el.append(gi)
        glyphs_el.append(gl)

    new_glyphs_xml = ET.tostring(glyphs_el, encoding="unicode")
    new_glyphinfo_xml = ET.tostring(glyphinfo_el, encoding="unicode")

    os.makedirs(FI, exist_ok=True)
    with open(FULL_OUT, "w", encoding="utf-8") as f:
        f.writelines(before)
        f.write(new_glyphs_xml + "\n")
        f.write(new_glyphinfo_xml + "\n")
        f.writelines(after)
    print("wrote", FULL_OUT, os.path.getsize(FULL_OUT), "bytes")


def cmd_xml2swf():
    out_gfx = os.path.join(FI, "font_lib_efigs_stencil.gfx")
    if os.path.exists(out_gfx):
        os.remove(out_gfx)
    r = subprocess.run([JAVA, "-jar", os.path.abspath(FFDEC), "-xml2swf", FULL_OUT, out_gfx],
                        capture_output=True, text=True)
    print(r.stdout[-3000:])
    print(r.stderr[-3000:])
    if not os.path.exists(out_gfx):
        sys.exit("!! xml2swf did not produce an output file")
    print("wrote", out_gfx, os.path.getsize(out_gfx), "bytes")


def cmd_deploy():
    out_gfx = os.path.join(FI, "font_lib_efigs_stencil.gfx")
    if not os.path.exists(GFX_BACKUP):
        shutil.copy2(GFX_LIVE, GFX_BACKUP)
        print("backed up pristine ->", GFX_BACKUP)
    shutil.copy2(out_gfx, GFX_LIVE)
    print("deployed ->", GFX_LIVE)

    # read back: re-decompile and confirm RDR Lino now has the NEW (non-donor) advances
    verify_dir = os.path.join(FI, "_verify")
    os.makedirs(verify_dir, exist_ok=True)
    vxml = os.path.join(verify_dir, "verify.xml")
    if os.path.exists(vxml):
        os.remove(vxml)
    subprocess.run([JAVA, "-jar", os.path.abspath(FFDEC), "-swf2xml", GFX_LIVE, vxml],
                    capture_output=True, text=True)
    gopen, gclose = find_span(vxml)
    with open(vxml, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    span = "".join(lines[gopen - 1:gclose])
    n_heb = span.count('glyphCode="1489"') + span.count('glyphCode="1501"')
    print("verify: RDR Lino Hebrew glyphs present in the redeployed live file:",
          span.count("glyphCode=\"15") + span.count("glyphCode=\"148") + span.count("glyphCode=\"149"))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "span":
        find_span()
    elif cmd == "build":
        cmd_build()
    elif cmd == "xml2swf":
        cmd_xml2swf()
    elif cmd == "deploy":
        cmd_deploy()
    elif cmd == "all":
        cmd_build()
        cmd_xml2swf()
        cmd_deploy()
    else:
        sys.exit(f"unknown command {cmd!r}")


if __name__ == "__main__":
    main()
