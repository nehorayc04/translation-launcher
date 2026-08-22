#!/usr/bin/env python3
r"""
unc_font.py — Hebrew glyph injector for UNCHARTED: Legacy of Thieves Collection.

The game's native text renderer uses **AngelCode BMFont** descriptors + **uncompressed
32-bit RGBA TGA** atlases (`data/fonts.psarc` -> `main.fnt` + `main_00.tga`).  This is the
friendliest font container met in this project: the descriptor is plain text and the atlas
has no block compression at all, so injection is "rasterise + append `char id=` lines".

Facts VERIFIED empirically against the shipped atlas (never assumed):
  * TGA is 32-bit **BGRA**, datatype 2 (uncompressed), **top-down** (imagedescriptor 0x20),
    18-byte header + 26-byte footer.  Rendering `A` straight out of `arr[y:y+h]` produced a
    clean upright 'A', so no row flip is needed.
  * `packed=1` -> every glyph lives in ONE colour channel; BMFont `chnl` maps
    **1=blue(byte0), 2=green(byte1), 4=red(byte2), 8=alpha(byte3)** — confirmed by decoding
    'A' (chnl=2) from byte1.
  * `main_00.tga` occupancy: blue/green/red are 95-98 % full, **alpha is 47.9 % used and
    rows 69..127 are 0 in the alpha plane** (max value 0) — i.e. genuinely free.
  * Latin metrics: size=42, lineHeight=42, **base=34**, padding=2 all round; caps have
    box height 30 and yoffset 6, so cap ink runs y=8..34 in line space = 26 px sitting
    exactly on the baseline.

Sizing rule (Hebrew has no x-height — it is all cap-height, so equal nominal px LOOKS
bigger than Latin): the STANDARD letters are scaled so their median ink height is
`BODY_RATIO * latin_cap_ink`, and every glyph is then cropped to its own ink box so that
lamed keeps its ascender and the finals keep their descenders.

Atlas growth: rows 0..127 are copied byte-for-byte and every existing `char` keeps its
exact x/y, so the shipped Latin is untouched; Hebrew goes into fresh rows below.  Growing
the atlas is safe *by evidence* — this game already ships `.fnt`/`.tga` pairs at 256x128,
256x256, 256x512, 512x512 and 1024x512, so the renderer reads the dimensions from data.
(The proof's pure-Latin marker is what would expose it if that were ever wrong.)

CLI:
    python unc_font.py info   <fnt> <tga>
    python unc_font.py inject <fnt> <tga> <out_fnt> <out_tga> [--font X.ttf] [--height 256]
    python unc_font.py verify <fnt> <tga>          # read the RESULT back, ASCII-render it
"""
import os
import re

import struct
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HEBREW = list(range(0x05D0, 0x05EB))          # 27 letters incl. the 5 finals
# letters whose ink is pure body (no ascender / no descender) — used to fix the scale
STANDARD = [c for c in HEBREW if c not in (0x05DC,                      # ל ascender
                                           0x05DA, 0x05DF, 0x05E3,      # ך ן ף descenders
                                           0x05E5, 0x05E7)]             # ץ ק descenders
BODY_RATIO = 0.85          # Hebrew body vs Latin cap ink height
PAD = 2                    # matches the shipped `padding=2,2,2,2`
SPACING = 3                # extra px folded into xadvance
CHNL = 8                   # alpha plane
SS = 4                     # supersample factor for rasterising

# --- edge profile, MEASURED against the shipped glyphs, not guessed -----------
# Of the INKED pixels of the shipped Latin (caps+lowercase), the coverage splits
# faint(1..25)=5.8% / mid(26..200)=16.8% / solid(>200)=77.4%.  Comparing raw box
# histograms is misleading because our crop is tighter than theirs, so the match is
# done CONDITIONAL ON INK.  A grid search over resampler x contrast x cut found:
#     BOX resampling + contrast stretch to 0.75  ->  4.9% / 16.9% / 78.2%
# i.e. an essentially identical edge.  LANCZOS was the wrong tool — its ringing
# produced 20.5% faint pixels, a 4x halo that is exactly the "noise/dots around the
# letters" failure seen on GoWR and Plague Tale.
RESAMPLE_BOX = True
CONTRAST_HI = 0.75         # coverage >= this becomes fully solid
FAINT_CUT = 0              # not needed once BOX+contrast is used

_DEF_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "plague_tale_requiem", "work", "font",
                         "fonts_pdf", "DavidLibre-Bold.ttf")


# ----------------------------------------------------------------------- BMFont
_CHAR_RE = re.compile(
    r'^char id=(\d+)\s+x=(\d+)\s+y=(\d+)\s+width=(\d+)\s+height=(\d+)'
    r'\s+xoffset=(-?\d+)\s+yoffset=(-?\d+)\s+xadvance=(-?\d+)\s+page=(\d+)\s+chnl=(\d+)', re.M)


def parse_fnt(text):
    info = dict(re.findall(r'(\w+)=(-?\d+)', re.search(r'^info .*', text, re.M).group(0)))
    common = dict(re.findall(r'(\w+)=(-?\d+)', re.search(r'^common .*', text, re.M).group(0)))
    chars = [dict(zip(("id", "x", "y", "w", "h", "xo", "yo", "xa", "page", "chnl"),
                      map(int, m.groups()))) for m in _CHAR_RE.finditer(text)]
    return {k: int(v) for k, v in info.items()}, {k: int(v) for k, v in common.items()}, chars


def latin_cap_ink(chars, info):
    caps = [c for c in chars if 65 <= c["id"] <= 90]
    hs = sorted(c["h"] for c in caps)
    return hs[len(hs) // 2] - 2 * int(info.get("padding", 2) and PAD)   # box - top/bottom padding


# ------------------------------------------------------------------------- TGA
def read_tga(path):
    d = open(path, "rb").read()
    idlen, cmaptype, dtype = d[0], d[1], d[2]
    w, h, bpp, desc = struct.unpack_from("<HHBB", d, 12)
    if (cmaptype, dtype, bpp) != (0, 2, 32):
        raise ValueError(f"unexpected TGA: cmap={cmaptype} type={dtype} bpp={bpp}")
    if not (desc & 0x20):
        raise ValueError("TGA is bottom-up; this injector expects top-down (desc bit 5)")
    px = 18 + idlen
    body = d[px:px + w * h * 4]
    arr = np.frombuffer(body, dtype=np.uint8).reshape(h, w, 4).copy()   # BGRA
    return dict(header=d[:px], arr=arr, footer=d[px + w * h * 4:], w=w, h=h, desc=desc)


def write_tga(t, arr, path):
    hdr = bytearray(t["header"])
    struct.pack_into("<HH", hdr, 12, arr.shape[1], arr.shape[0])
    with open(path, "wb") as fh:
        fh.write(bytes(hdr)); fh.write(arr.tobytes()); fh.write(t["footer"])


# ---------------------------------------------------------------- rasterising
def _render(font, cp, ss):
    """-> (coverage uint8 HxW at supersample, ink bbox, baseline row) or None."""
    pad = 40 * ss
    img = Image.new("L", (pad * 3, pad * 3), 0)
    dr = ImageDraw.Draw(img)
    base = (pad * 2, pad * 2)
    dr.text(base, chr(cp), fill=255, font=font, anchor="ls")   # 'ls' = left / baseline
    bb = img.getbbox()
    if bb is None:
        return None
    return np.asarray(img), bb, base[1]


def build_glyphs(font_path, body_px, ss=SS):
    """-> {cp: dict(cov=HxW uint8, w, h, ascent)}  ascent = px of ink ABOVE the baseline."""
    # 1) find the pixel size whose STANDARD-letter median ink height == body_px
    lo, hi = 4, 200
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid * ss)
        hs = []
        for cp in STANDARD:
            r = _render(f, cp, ss)
            if r:
                _a, bb, _b = r
                hs.append((bb[3] - bb[1]) / ss)
        med = sorted(hs)[len(hs) // 2]
        best = (mid, med)
        if abs(med - body_px) <= 0.5:
            break
        if med < body_px:
            lo = mid + 1
        else:
            hi = mid - 1
    size = best[0]

    f = ImageFont.truetype(font_path, size * ss)
    out = {}
    for cp in HEBREW:
        r = _render(f, cp, ss)
        if r is None:
            raise ValueError(f"donor font has no glyph for U+{cp:04X}")
        arr, bb, baseline = r
        x0, y0, x1, y1 = bb
        crop = arr[y0:y1, x0:x1]
        # downsample the supersampled coverage — BOX (area average), never LANCZOS
        img = Image.fromarray(crop).resize((max(1, round((x1 - x0) / ss)),
                                            max(1, round((y1 - y0) / ss))),
                                           Image.BOX if RESAMPLE_BOX else Image.LANCZOS)
        cov = np.asarray(img).astype(np.float32) / 255.0
        cov = np.clip(cov / CONTRAST_HI, 0.0, 1.0)          # match the shipped edge
        cov = (cov * 255.0).round().astype(np.uint8)
        if FAINT_CUT:
            cov[cov < FAINT_CUT] = 0
        out[cp] = dict(cov=cov, w=cov.shape[1], h=cov.shape[0],
                       ascent=(baseline - y0) / ss)
    return out, size


# ------------------------------------------------------------------- packing
def pack(glyphs, atlas_w, y_start, y_end, gap=2):
    """Shelf-pack the glyph boxes into [y_start, y_end). -> {cp: (x, y)} or None."""
    order = sorted(glyphs, key=lambda cp: -(glyphs[cp]["h"] + 2 * PAD))
    place, x, y, shelf = {}, 0, y_start, 0
    for cp in order:
        bw = glyphs[cp]["w"] + 2 * PAD
        bh = glyphs[cp]["h"] + 2 * PAD
        if x + bw > atlas_w:
            y += shelf + gap
            x, shelf = 0, 0
        if y + bh > y_end:
            return None
        place[cp] = (x, y)
        x += bw + gap
        shelf = max(shelf, bh)
    return place


# -------------------------------------------------------------------- inject
def inject(fnt_text, tga_path, font_path=None, new_height=256):
    info, common, chars = parse_fnt(fnt_text)
    t = read_tga(tga_path)
    W, H = t["w"], t["h"]
    if new_height < H:
        raise ValueError("new_height must be >= current atlas height")

    cap = latin_cap_ink(chars, info)
    body = max(6, round(cap * BODY_RATIO))
    glyphs, size = build_glyphs(font_path or _DEF_FONT, body)

    # grow the atlas: rows 0..H-1 stay byte-identical, Hebrew lands below
    arr = np.zeros((new_height, W, 4), dtype=np.uint8)
    arr[:H] = t["arr"]
    place = pack(glyphs, W, H, new_height)
    if place is None:
        raise ValueError("Hebrew glyphs do not fit in the new atlas rows — raise --height")

    plane = {1: 0, 2: 1, 4: 2, 8: 3}[CHNL]
    base = int(common["base"])
    new_lines = []
    for cp in HEBREW:
        g = glyphs[cp]
        x, y = place[cp]
        arr[y + PAD:y + PAD + g["h"], x + PAD:x + PAD + g["w"], plane] = g["cov"]
        yoff = base - PAD - int(round(g["ascent"]))
        new_lines.append(
            f'char id={cp}      x={x}    y={y}    width={g["w"] + 2 * PAD}    '
            f'height={g["h"] + 2 * PAD}    xoffset={-PAD}    yoffset={yoff}    '
            f'xadvance={g["w"] + SPACING}    page=0  chnl={CHNL}')

    # rewrite the descriptor: chars count, atlas height, append the new char lines
    out = fnt_text
    out = re.sub(r'(^common [^\n]*?scaleH=)(\d+)', lambda m: m.group(1) + str(new_height), out, flags=re.M)
    out = re.sub(r'(^chars count=)(\d+)',
                 lambda m: m.group(1) + str(len(chars) + len(new_lines)), out, flags=re.M)
    nl = "\r\n" if "\r\n" in out else "\n"
    last = list(_CHAR_RE.finditer(out))[-1]
    out = out[:last.end()] + nl + nl.join(new_lines) + out[last.end():]
    return out, arr, t, dict(size=size, body=body, cap=cap, count=len(new_lines))


# ----------------------------------------------------------------------- CLI
def _cmd_info(a):
    info, common, chars = parse_fnt(open(a.fnt, encoding="utf-8", errors="replace").read())
    t = read_tga(a.tga)
    print(f"face={info}  common={common}")
    print(f"chars={len(chars)}  atlas={t['w']}x{t['h']} desc=0x{t['desc']:02x}")
    print(f"latin cap ink = {latin_cap_ink(chars, info)} px  -> hebrew body target {round(latin_cap_ink(chars,info)*BODY_RATIO)} px")
    occ = {c: 0 for c in (1, 2, 4, 8)}
    for c in chars:
        occ[c["chnl"]] = occ.get(c["chnl"], 0) + c["w"] * c["h"]
    print("per-channel box area:", occ)


def _cmd_inject(a):
    txt = open(a.fnt, encoding="utf-8", errors="replace").read()
    out, arr, t, meta = inject(txt, a.tga, a.font, a.height)
    open(a.out_fnt, "w", encoding="utf-8", newline="").write(out)
    write_tga(t, arr, a.out_tga)
    print(f"injected {meta['count']} Hebrew glyphs @ donor size {meta['size']}px "
          f"(body {meta['body']}px vs latin cap {meta['cap']}px)")
    print(f"  {a.out_fnt}  ({os.path.getsize(a.out_fnt):,} B)")
    print(f"  {a.out_tga}  {arr.shape[1]}x{arr.shape[0]}  ({os.path.getsize(a.out_tga):,} B)")


def _cmd_verify(a):
    """Read the RESULT back off disk and ASCII-render it — never trust the builder."""
    info, common, chars = parse_fnt(open(a.fnt, encoding="utf-8", errors="replace").read())
    t = read_tga(a.tga)
    by = {c["id"]: c for c in chars}
    missing = [cp for cp in HEBREW if cp not in by]
    print(f"atlas {t['w']}x{t['h']}  chars={len(chars)}  hebrew present={27-len(missing)}/27")
    if missing:
        print("  MISSING:", [f"U+{c:04X}" for c in missing])
    bad = 0
    for cp in HEBREW:
        c = by.get(cp)
        if not c:
            continue
        plane = {1: 0, 2: 1, 4: 2, 8: 3}[c["chnl"]]
        g = t["arr"][c["y"]:c["y"] + c["h"], c["x"]:c["x"] + c["w"], plane]
        if g.max() < 40:
            bad += 1
            print(f"  U+{cp:04X} BLANK in its declared plane!")
        # neighbour bleed: ring outside the box must be clean in the same plane
        y0, y1 = max(0, c["y"] - 3), min(t["h"], c["y"] + c["h"] + 3)
        x0, x1 = max(0, c["x"] - 3), min(t["w"], c["x"] + c["w"] + 3)
        ring = t["arr"][y0:y1, x0:x1, plane].astype(int).sum() - g.astype(int).sum()
        if ring > 0:
            print(f"  U+{cp:04X} ring ink {ring} (possible neighbour bleed)")
    print(f"blank glyphs: {bad}")
    for cp in (0x05D0, 0x05DE, 0x05E9, 0x05DC, 0x05E7):
        c = by[cp]
        plane = {1: 0, 2: 1, 4: 2, 8: 3}[c["chnl"]]
        g = t["arr"][c["y"]:c["y"] + c["h"], c["x"]:c["x"] + c["w"], plane]
        print(f"\nU+{cp:04X} {chr(cp)}  box={c['w']}x{c['h']} yoff={c['yo']} xadv={c['xa']}")
        for r in range(0, g.shape[0], 2):
            print("   " + "".join("#" if v > 140 else ("+" if v > 50 else ".") for v in g[r]))


def main():
    ap = argparse.ArgumentParser(description="UNCHARTED LoT Hebrew font injector")
    s = ap.add_subparsers(dest="cmd", required=True)
    q = s.add_parser("info");   q.add_argument("fnt"); q.add_argument("tga")
    q = s.add_parser("inject"); q.add_argument("fnt"); q.add_argument("tga")
    q.add_argument("out_fnt"); q.add_argument("out_tga")
    q.add_argument("--font", default=None); q.add_argument("--height", type=int, default=256)
    q = s.add_parser("verify"); q.add_argument("fnt"); q.add_argument("tga")
    a = ap.parse_args()
    {"info": _cmd_info, "inject": _cmd_inject, "verify": _cmd_verify}[a.cmd](a)


if __name__ == "__main__":
    main()
