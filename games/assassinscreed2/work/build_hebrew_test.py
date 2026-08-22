#!/usr/bin/env python3
"""
AC2 Hebrew RTL menu PROOF build (clean, English-preserving).

Hijacks the ProBold Cyrillic atlas (Russian CharacterSet): paints Hebrew letters
over 9 Cyrillic glyph cells whose codepoints never occur in English UI text, so
ONLY our menu strings (stored as those Cyrillic codepoints, visual/RTL order)
render Hebrew while all English stays intact. No registry/language change needed.

Outputs MODIFIED COPIES of DataPC.forge + DataPC_extra.forge to OUT_DIR and
verifies them by full re-decode. A separate deploy step copies them into the game.
"""
import sys, os, json, shutil, struct, subprocess
from PIL import Image, ImageFont, ImageDraw
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import ac2_forge, ac2_font, ac2_loc, ac2_locwrite
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = r"D:/Games/Assassin's Creed II"
OUT = r"c:/tmp/ac2_he_build"
TEXCONV = r"C:/Users/Nehoray_Cohen/Downloads/AnvilToolkit_Release_v1.2.10-20-1-2-10-1722530650/Utils/texconv.exe"
HEB_FONT = r"C:/Windows/Fonts/arialbd.ttf"
RUS_ATLAS = "AC2Aaux_ProBold_RussianCharacterSet_1_MapDesc"

# Hebrew letter -> Cyrillic codepoint (glyph cell we repaint). Verified rus_match.
HEB2CYR = {
    "ה": 0x0410,  # ה -> А
    "מ": 0x0412,  # מ -> В
    "ש": 0x0415,  # ש -> Е
    "ך": 0x041A,  # ך -> К
    "ג": 0x041D,  # ג -> Н
    "ד": 0x041E,  # ד -> О
    "ר": 0x0420,  # ר -> Р
    "ו": 0x0421,  # ו -> С
    "ת": 0x0425,  # ת -> Х
}
CYR2HEB = {v: k for k, v in HEB2CYR.items()}

# Cyrillic codepoint -> atlas blob index (from rus_match verification)
CYR_BLOB = {0x0410: 20, 0x0412: 99, 0x0415: 23, 0x041A: 249, 0x041D: 74,
            0x041E: 101, 0x0420: 251, 0x0421: 3, 0x0425: 9}

# menu edits: id -> Hebrew word (logical order). Stored reversed (visual) as Cyrillic.
MENU = {
    276689: "המשך",          # המשך  (Resume)
    276696: "הגדרות",  # הגדרות (Options)
}


def heb_to_cyr_visual(word):
    """Hebrew logical -> reversed (visual LTR) string of mapped Cyrillic codepoints."""
    return "".join(chr(HEB2CYR[ch]) for ch in reversed(word))


def render_glyph(letter, w, h):
    """Render a Hebrew letter as an alpha mask fitted into a w x h cell."""
    big = 200
    im = Image.new("L", (big, big), 0)
    fnt = ImageFont.truetype(HEB_FONT, 150)
    d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), letter, font=fnt)
    gw, gh = bb[2]-bb[0], bb[3]-bb[1]
    d.text((-bb[0] + (big-gw)//2, -bb[1] + (big-gh)//2), letter, font=fnt, fill=255)
    a = np.array(im)
    ys, xs = np.where(a > 40)
    a = a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    g = Image.fromarray(a)
    # fit into cell with a small margin, preserve aspect
    mw, mh = max(1, w-2), max(1, h-2)
    gw, gh = g.size
    sc = min(mw/gw, mh/gh)
    g = g.resize((max(1, int(gw*sc)), max(1, int(gh*sc))))
    cell = Image.new("L", (w, h), 0)
    cell.paste(g, ((w-g.size[0])//2, (h-g.size[1])//2))
    return cell


def build_font():
    fg, idx, at = ac2_font.load(os.path.join(GAME, "DataPC_extra.forge"), RUS_ATLAS)
    img = ac2_font.decode_image(at).convert("RGBA")
    boxes = json.load(open(os.path.join(os.path.dirname(__file__), "..", "rus_boxes.json"))) \
        if os.path.exists(os.path.join(os.path.dirname(__file__), "..", "rus_boxes.json")) \
        else json.load(open(r"c:/tmp/rus_boxes.json"))
    A = np.array(img)
    for cp, blob in CYR_BLOB.items():
        x0, y0, x1, y1 = boxes[blob]
        w, h = x1-x0+1, y1-y0+1
        A[y0:y1+1, x0:x1+1, :] = 0                      # clear cell
        glyph = np.array(render_glyph(CYR2HEB[cp], w, h))
        A[y0:y1+1, x0:x1+1, 0] = 255                    # white RGB
        A[y0:y1+1, x0:x1+1, 1] = 255
        A[y0:y1+1, x0:x1+1, 2] = 255
        A[y0:y1+1, x0:x1+1, 3] = glyph                  # alpha = coverage
    Image.fromarray(A, "RGBA").save(os.path.join(OUT, "rus_edited.png"))
    # encode to BC3 via texconv
    subprocess.run([TEXCONV, "-nologo", "-f", "BC3_UNORM", "-m", "1", "-y",
                    "-o", OUT.replace("/", "\\"), os.path.join(OUT, "rus_edited.png").replace("/", "\\")],
                   check=True, capture_output=True)
    dds = open(os.path.join(OUT, "rus_edited.dds"), "rb").read()
    body = dds[128:128 + at.texsize]
    assert len(body) == at.texsize, (len(body), at.texsize)
    new_res = at.rebuild(body)
    return idx, new_res, at


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # ---- FONT (DataPC_extra.forge) ----
    fidx, fres, at = build_font()
    extra_src = os.path.join(GAME, "DataPC_extra.forge")
    extra_out = os.path.join(OUT, "DataPC_extra.forge")
    print("copying DataPC_extra.forge ...")
    shutil.copy(extra_src, extra_out)
    ac2_forge.Forge.write_resource(extra_out, fidx, fres)
    # verify font decode
    fg2, i2, at2 = ac2_font.load(extra_out, RUS_ATLAS)
    print("font written; reread dims", at2.width, at2.height, "tex match-size", at2.texsize == at.texsize)

    # ---- LOC (DataPC.forge) ----
    main_src = os.path.join(GAME, "DataPC.forge")
    main_out = os.path.join(OUT, "DataPC.forge")
    fgm = ac2_forge.Forge(main_src)
    li = fgm.by_name("LocalizationPackage_English")
    slot, off, nxt = fgm.full_slot(li)
    edits = {sid: heb_to_cyr_visual(word) for sid, word in MENU.items()}
    for sid, word in MENU.items():
        print(f"  loc {sid}: {word}  ->  visual cyr {edits[sid]!r}")
    new_loc = ac2_locwrite.rebuild(slot, edits)
    print("copying DataPC.forge ...")
    shutil.copy(main_src, main_out)
    ac2_forge.Forge.write_resource(main_out, li, new_loc)
    # verify loc decode
    fgm2 = ac2_forge.Forge(main_out)
    s2, o2, n2 = fgm2.full_slot(fgm2.by_name("LocalizationPackage_English"))
    d = dict(ac2_loc.decode_payload(ac2_locwrite._find_cfd2(s2)[2])[2])
    ok = all(d[sid] == edits[sid] for sid in edits)
    print("loc written; edits verified:", ok)
    print("\nBUILD DONE ->", OUT)
    print("  DataPC.forge       (loc: 2 menu strings)")
    print("  DataPC_extra.forge (font: 9 Hebrew glyphs in Cyrillic cells)")


if __name__ == "__main__":
    main()
