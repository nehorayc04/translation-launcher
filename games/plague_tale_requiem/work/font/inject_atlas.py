#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_atlas.py — draw REAL Hebrew glyphs into BIG_ARABIC's DXT5 atlas and
repurpose 27 Arabic glyph slots to the Hebrew letters (U+05D0-05EA).

Why repurpose Arabic slots: the atlas pages are full, but the Arabic glyphs are
never looked up in a Hebrew translation (the Arabic-slot text is Hebrew, tokens
are Latin, digits are Latin). So each Hebrew letter takes over an Arabic entry:
  * cid  Arabic -> Hebrew
  * box  -> a sub-rect inside the Arabic glyph's box (uniform height -> uniform
           on-screen size), where we paint the Hebrew glyph
  * metrics (topY / bearing) set so all Hebrew sits on one baseline
The atlas is BC3/DXT5 (glyph coverage in the ALPHA channel, colour = black).
We only rewrite the ALPHA sub-block of the touched 4x4 blocks and PRESERVE the
colour sub-block, so nothing else on the page changes.

Metric model (measured from Latin glyphs, see notes):
  float#1 ("topY") = distance from the text line top to the box TOP.
  baseline ~= lineTop + 130 (o/n/x box-bottom). A cap box-bottom ~= baseline.
  advance ~= box_width + bearingX.
So for a Hebrew cell of height H sitting on the baseline: topY = BASELINE - H.
"""
from __future__ import annotations
import argparse, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from dpc_repack import DpcRepack
from fonts_z import FontsZ, char_to_cid, cid_to_char

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BIG_ARABIC_ID = 0xAFBE3792DDA3B358
TEX_CLASS = 0xE9659CD1C3F3326D
HEBREW = [chr(c) for c in range(0x05D0, 0x05EB)]  # א..ת (27)
BACKUP = ".he_backup"
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")

# placement
CELL_H = 74           # uniform Hebrew cell height (px in atlas)
MAX_W = 48            # max glyph width (fits Arabic boxes >=50 wide)
BASELINE = 130        # lineTop -> baseline (px), measured from o/n
BODY_H = 60           # target Hebrew body height inside the cell
BEAR_X = 4.0          # letter spacing added to advance
DEF_FONT = r"C:\Windows\Fonts\FRANKB.TTF"   # Frank Ruehl Bold — dark serif


# ------------------------- BC3 / DXT5 alpha codec ------------------------- #
def _alpha_lut(a0, a1):
    if a0 > a1:
        return [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    return [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]


def decode_alpha(data, W=512, H=512):
    out = np.zeros((H, W), np.uint8)
    bpr = W // 4
    for by in range(H // 4):
        for bx in range(bpr):
            o = (by * bpr + bx) * 16
            lut = _alpha_lut(data[o], data[o + 1])
            bits = int.from_bytes(data[o + 2:o + 8], "little")
            for i in range(16):
                out[by * 4 + i // 4, bx * 4 + i % 4] = lut[(bits >> (3 * i)) & 7]
    return out


_ENC_LUT = _alpha_lut(255, 0)  # fixed endpoints a0=255,a1=0
_COL_LUT = [255, 0, 170, 85]   # BC1 c0=white>c1=black -> [c0, c1, 2/3, 1/3]


def encode_alpha_block(cell):  # cell: 4x4 uint8 -> 8-byte DXT5 alpha block
    bits = 0
    for i in range(16):
        v = int(cell[i // 4, i % 4])
        idx = min(range(8), key=lambda k: abs(_ENC_LUT[k] - v))
        bits |= idx << (3 * i)
    return bytes([255, 0]) + bits.to_bytes(6, "little")


def encode_block(cell):
    """Full 16-byte DXT5 block with the glyph in BOTH alpha AND colour (the atlas
    stores the glyph in both channels; the font shader uses colour×alpha, so a
    colour left as the old glyph mixed with a new alpha renders as noise)."""
    alpha = encode_alpha_block(cell)
    cbits = 0
    for i in range(16):
        v = int(cell[i // 4, i % 4])
        idx = min(range(4), key=lambda k: abs(_COL_LUT[k] - v))
        cbits |= idx << (2 * i)
    colour = struct.pack("<HH", 0xFFFF, 0x0000) + cbits.to_bytes(4, "little")
    return alpha + colour


# ------------------------------- font render ------------------------------ #
def _fit_font(path):
    """font size so a reference Hebrew letter body ~= BODY_H."""
    for size in range(BODY_H, BODY_H * 3):
        f = ImageFont.truetype(path, size)
        b = f.getbbox("ה")            # (l,t,r,b)
        if (b[3] - b[1]) >= BODY_H:
            return f
    return ImageFont.truetype(path, BODY_H * 2)


def render_letter(font, ch):
    """render ch to a tight alpha array (h=CELL_H), baseline near cell bottom."""
    tmp = Image.new("L", (MAX_W * 4, CELL_H * 4), 0)
    d = ImageDraw.Draw(tmp)
    # draw at baseline anchor 'ls' would be ideal; use manual placement
    b = font.getbbox(ch)
    gw = b[2] - b[0]
    # baseline y inside CELL_H: leave 8px for descenders
    base_y = CELL_H - 8
    d.text((2 - b[0], base_y - font.getbbox(ch)[3]), ch, fill=255, font=font)
    arr = np.array(tmp.crop((0, 0, MAX_W, CELL_H)))
    # tight width
    cols = np.where(arr.max(axis=0) > 8)[0]
    if len(cols):
        w = min(MAX_W, int(cols.max()) + 3)
    else:
        w = 12
    return arr[:, :w], w


# --------------------------------- main ----------------------------------- #
def resolve_mat_textures(byid, fz):
    mats = list(struct.unpack_from("<10Q", fz.tail, 4))
    texids = {o.oid for o in byid.values() if o.otype == TEX_CLASS}
    m2t = {}
    for i, mid in enumerate(mats):
        b = byid[mid].info + byid[mid].body
        for off in range(0, len(b) - 8):
            v = struct.unpack_from("<Q", b, off)[0]
            if v in texids:
                m2t[i] = v
                break
    return m2t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpc", default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--font", default=DEF_FONT)
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--verify", action="store_true", help="decode result -> PNGs")
    args = ap.parse_args()

    if args.revert:
        bak = args.dpc + BACKUP
        if os.path.exists(bak):
            import shutil; shutil.copy2(bak, args.dpc); print("reverted from", bak)
        else:
            print("no backup:", bak)
        return

    # ALWAYS build from the pristine backup (idempotent), fall back to live file
    src = args.dpc + BACKUP if os.path.exists(args.dpc + BACKUP) else args.dpc
    D = DpcRepack(src)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fm = byid[BIG_ARABIC_ID]
    fz = FontsZ(fm.body)
    m2t = resolve_mat_textures(byid, fz)

    # pick 27 Arabic entries with the largest boxes
    def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF
    cand = [e for e in fz.entries
            if (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid))
            and (e.x1 - e.x0) >= 50 and (e.y1 - e.y0) >= CELL_H]
    cand.sort(key=lambda e: -(e.x1 - e.x0) * (e.y1 - e.y0))
    targets = cand[:27]
    assert len(targets) == 27, f"only {len(targets)} slots"

    font = _fit_font(args.font)
    print(f"font: {os.path.basename(args.font)}  size≈{font.size}")

    # plan per-page paints: page_id -> list of (x0,y0, alpha_subarray)
    paints = {}
    plan = []   # (entry, heb_char, mat, tex_id, sub_x0,sub_y0,sub_x1,sub_y1)
    for e, ch in zip(targets, HEBREW):
        tex = m2t[e.mat]
        glyph, gw = render_letter(font, ch)
        x0, y0 = int(e.x0), int(e.y0)
        sub = (x0, y0, x0 + gw, y0 + CELL_H)
        paints.setdefault(tex, []).append((x0, y0, glyph))
        plan.append((e, ch, e.mat, tex, sub))

    # apply paints to each affected texture (decode alpha, paint, re-encode touched
    # blocks; keep colour sub-block; keep untouched blocks byte-identical)
    for tex_id, plist in paints.items():
        t = byid[tex_id]
        raw = t.body                      # 4-byte header + 512*512 DXT5
        head, blocks = raw[:4], bytearray(raw[4:])
        alpha = decode_alpha(blocks)
        touched = set()
        for (x0, y0, glyph) in plist:
            gh, gw = glyph.shape
            alpha[y0:y0 + gh, x0:x0 + gw] = glyph
            for yy in range(y0, y0 + gh):
                for xx in range(x0, x0 + gw):
                    touched.add((yy // 4, xx // 4))
        bpr = 512 // 4
        for (by, bx) in touched:
            o = (by * bpr + bx) * 16
            cell = alpha[by * 4:by * 4 + 4, bx * 4:bx * 4 + 4]
            blocks[o:o + 8] = encode_alpha_block(cell)   # colour block [o+8:o+16] preserved
        t.body = head + bytes(blocks)
        t.dirty = True
        print(f"  page {tex_id:016X}: {len(plist)} glyphs, {len(touched)} blocks re-encoded")

    # ADD 27 new Hebrew entries pointing at the drawn glyphs (proven-working lookup
    # path — the marker test showed appended entries ARE found; repurposing an
    # existing Arabic entry's cid in place is NOT picked up by the engine's map).
    # The original Arabic entries stay (their pixels are now Hebrew, never looked up).
    for (e, ch, mat, tex, sub) in plan:
        ne = e.copy()
        ne.cid = char_to_cid(ch)
        ne.x0, ne.y0, ne.x1, ne.y1 = float(sub[0]), float(sub[1]), float(sub[2]), float(sub[3])
        ne.adv = float(BASELINE - CELL_H)   # float#1 = topY
        ne.bx = BEAR_X
        ne.by = 2.0
        fz.entries.append(ne)
    fm.body = fz.build()
    fm.dirty = True

    rebuilt = D.build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ENGLISH_he.DPC")
    open(out, "wb").write(rebuilt)
    print(f"rebuilt: {len(rebuilt)} bytes (src {len(D.data)}, delta {len(rebuilt)-len(D.data):+d})")
    print("wrote", out)

    if args.verify:
        _verify(out, plan)

    if args.deploy:
        import shutil
        bak = args.dpc + BACKUP
        if not os.path.exists(bak):
            shutil.copy2(args.dpc, bak); print("backed up ->", bak)
        shutil.copy2(out, args.dpc); print("DEPLOYED ->", args.dpc)


def _verify(path, plan):
    """re-parse built DPC, decode a couple of edited pages, save PNGs."""
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fm = byid[BIG_ARABIC_ID]; fz = FontsZ(fm.body)
    heb_entries = [e for e in fz.entries if 0xD790 <= e.cid <= 0xD7AA]
    print(f"VERIFY: FontMap glyphs={len(fz.entries)} hebrew entries={len(heb_entries)}")
    # render each hebrew glyph's sub-rect into a contact sheet
    pages = {}
    for e in heb_entries:
        # find its texture via material
        pass
    # decode the first two edited pages and crop the hebrew boxes
    tex_ids = sorted({t for (_, _, _, t, _) in plan})
    sheet = Image.new("L", (28 * (MAX_W + 6), CELL_H + 12), 30)
    x = 4
    m2t = resolve_mat_textures(byid, fz)
    for e in sorted(heb_entries, key=lambda e: e.cid):
        tex = m2t[e.mat]
        raw = byid[tex].body
        alpha = decode_alpha(bytearray(raw[4:]))
        crop = alpha[int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        sheet.paste(Image.fromarray(crop, "L"), (x, 6))
        x += crop.shape[1] + 6
    p = os.path.join(SC, "hebrew_atlas_sheet.png")
    sheet.save(p)
    print("saved contact sheet:", p)


if __name__ == "__main__":
    main()
