"""FC5 Hebrew font injector -- adds the 27 Hebrew letters to the game's ARABIC font while
keeping every original glyph PIXEL- and METRIC-identical.

Chain (all of it proven for FC5):
    d27eb425d5b53ec6 (font SWF)  maps  arabic -> UI\\Common\\fonts\\Fire\\DIN_Mittelschrift_LT_W1G_Arabic.ffd
    that .ffd (236295edc3a3045b) points at
    UI\\Common\\fonts\\Fire\\DIN_Mittelschrift_LT_W1G_Arabic_1.xbt  (4121034366bd73a3)
FFDConverter (-v FC5) round-trips .ffd <-> .fnt, so the metrics are editable text.

!! Build from the copy in patch.fat -- it OVERRIDES common.fat and is a different font
   (1,094 glyphs / R8+mips) than common's (953 / BC3).  See pull_font.py.

The atlas is FULL, so it grows 1024x1024 -> 1024x2048 (power of two, like every other atlas
the game ships).  It is UNCOMPRESSED R8 with a mip chain, so the original 1,048,576 bytes of
level 0 are spliced in byte-for-byte and only the new lower half is generated; the mip chain
is regenerated (its dimensions necessarily change with the base).

Nothing is guessed: the SDF encoding and the advance quantisation are FITTED from the game's
own glyphs.

  python -u fc5_font.py [ttf-key] [body_px]   -> extract/hebrew.fnt + extract/hebrew.xbt
"""
import sys, os, re, struct

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from PIL import Image, ImageFont, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "extract")

ATLAS_W, ORIG_H, NEW_H = 1024, 1024, 2048
DDS_OFF_FIELD = 8            # TBX+8 holds the offset of the DDS header
ADV_Q = 1.3                  # xadvance grid, FITTED over every shipped glyph (residual .006)
HEBREW = list(range(0x05D0, 0x05EB))          # the 27 letters (incl. the 5 finals)
SS = 8                       # supersample for an accurate distance field
MARGIN = 6                   # px of SDF falloff room around the ink
PAD4 = 8                     # keep glyphs clear of each other's falloff

FONTS = {
    "heebo":     r"games/spiderman2/extracted/_heebo/Heebo-Medium.ttf",
    "heebo-reg": r"games/spiderman2/extracted/_heebo/Heebo-Regular.ttf",
    "assistant": r"C:/Windows/Fonts/Assistant-Regular.ttf",
    "arial":     r"C:/Windows/Fonts/arial.ttf",
    "arialbd":   r"C:/Windows/Fonts/arialbd.ttf",
    "david":     r"C:/Windows/Fonts/david.ttf",
}
_INF = 1e20


# ------------------------------------------------------------------ SDF
def _edt1d(f):
    n = len(f); d = np.empty(n); v = np.zeros(n, int); z = np.empty(n + 1)
    k = 0; v[0] = 0; z[0] = -_INF; z[1] = _INF
    for q in range(1, n):
        s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k])
        while s <= z[k]:
            k -= 1
            s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k])
        k += 1; v[k] = q; z[k] = s; z[k + 1] = _INF
    k = 0
    for q in range(n):
        while z[k + 1] < q:
            k += 1
        d[q] = (q - v[k]) * (q - v[k]) + f[v[k]]
    return d


def _edt(mask):
    f = np.where(mask, 0.0, _INF)
    for i in range(f.shape[0]):
        f[i] = _edt1d(f[i])
    for j in range(f.shape[1]):
        f[:, j] = _edt1d(f[:, j].copy())
    return np.sqrt(f)


def signed_distance(mask):
    return _edt(~mask) - _edt(mask)            # + inside, - outside


# ------------------------------------------------------------------ atlas I/O
def mip_sizes(w, h):
    out = []
    while True:
        out.append((w, h))
        if w == 1 and h == 1:
            break
        w = max(1, w // 2); h = max(1, h // 2)
    return out


class Atlas:
    """TBX-wrapped DDS, R8_UNORM (dxgiFormat 61) with a full mip chain."""

    def __init__(self, path):
        self.raw = raw = open(path, "rb").read()
        assert raw[:4] == b"TBX\x00", raw[:4]
        self.o = o = struct.unpack_from("<I", raw, DDS_OFF_FIELD)[0]
        assert raw[o:o + 4] == b"DDS "
        self.h, self.w = struct.unpack_from("<II", raw, o + 12)
        self.mips = struct.unpack_from("<I", raw, o + 28)[0]
        self.fourcc = raw[o + 84:o + 88]
        self.ext = 20 if self.fourcc == b"DX10" else 0
        self.fmt = struct.unpack_from("<I", raw, o + 128)[0] if self.ext else None
        assert self.fmt == 61, f"expected R8_UNORM(61), got {self.fmt}"
        self.body_off = o + 128 + self.ext
        body = raw[self.body_off:]
        assert len(body) == sum(a * b for a, b in mip_sizes(self.w, self.h)), len(body)
        self.mip0 = np.frombuffer(body[:self.w * self.h], np.uint8).reshape(self.h, self.w)

    def rebuild(self, mip0):
        """Header + regenerated mip chain for a new level-0 (same width, taller)."""
        h, w = mip0.shape
        levels = [mip0]
        cw, ch = w, h
        while not (cw == 1 and ch == 1):
            nw, nh = max(1, cw // 2), max(1, ch // 2)
            cur = levels[-1].astype(np.uint16)
            # box filter; an SDF averages gracefully, which is why mips are safe here
            cur = cur[:nh * (ch // nh), :nw * (cw // nw)]
            cur = cur.reshape(nh, ch // nh, nw, cw // nw).mean(axis=(1, 3))
            levels.append(np.clip(cur + 0.5, 0, 255).astype(np.uint8))
            cw, ch = nw, nh
        hdr = bytearray(self.raw[:self.body_off])
        struct.pack_into("<I", hdr, self.o + 12, h)          # dwHeight
        struct.pack_into("<I", hdr, self.o + 16, w)          # dwWidth
        struct.pack_into("<I", hdr, self.o + 28, len(levels))  # dwMipMapCount
        return bytes(hdr) + b"".join(l.tobytes() for l in levels), len(levels)


# ------------------------------------------------------------------ metrics
def parse_fnt(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in re.finditer(r"char id=(\d+)\s+x=([\d.\-]+)\s+y=([\d.\-]+)\s+width=([\d.\-]+)\s+"
                         r"height=([\d.\-]+)\s+xoffset=([\d.\-]+)\s+yoffset=([\d.\-]+)\s+"
                         r"xadvance=([\d.\-]+)", t):
        out[int(m.group(1))] = tuple(float(m.group(i)) for i in range(2, 9))
    return out


# --- matching Far Cry 6 -------------------------------------------------------------
# FC6 merges Heebo OUTLINES into its own TrueType UI fonts (fc6_font._add_hebrew scales the
# donor to the target's upem), so Hebrew there keeps its NATURAL Heebo size AND its NATURAL
# Heebo advances, as a fraction of the em.  Measured from FC6's real fonts:
#     Noto Kufi Arabic (the font its Arabic-locale menu renders with)  alef = 0.7598 em
# and Heebo-Medium's Hebrew body is 0.5850 em, so FC6 draws  hebrew : arabic-alef = 0.770.
# Anchoring on the ARABIC is what makes this transfer: both games put Hebrew in the Arabic
# slot beside Arabic text, and it needs no guess about either Latin font's cap/em.
FC6_KUFI_ALEF_EM = 0.7598


def measure_advance_unit(chars):
    """The advance field's unit, in units per atlas PIXEL, measured from the game's OWN
    Latin glyphs -- rect/offsets are in px but xadvance is not.

    NOT by comparing against a reference TTF: the donor (Heebo) is wider than the game's
    condensed DIN, so that comparison folds the width difference into the constant and
    squeezes Hebrew to ~73% of its natural width.  Instead recover it geometrically:
    the SDF margin is 'A's -xoffset (DIN's 'A' has ~0 left bearing), ink = rect - 2*margin,
    left bearing = xoffset + margin, and for these letters the bearings are symmetric."""
    margin = -chars[65][4]
    us = []
    for c in "AHMNOTXonesu":
        k = ord(c)
        if k not in chars:
            continue
        _, _, w, _, xo, _, adv = chars[k]
        ink = w - 2 * margin
        adv_px = ink + 2 * (xo + margin)
        if adv_px > 1 and adv > 0:
            us.append(adv / adv_px)
    us.sort()
    return margin, us[len(us) // 2]


def hebrew_body_em(ttf_path):
    """Heebo's own body height as a fraction of the em -- the size FC6 renders at."""
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen
    ft = TTFont(ttf_path)
    gs, cm, em = ft.getGlyphSet(), ft.getBestCmap(), ft["head"].unitsPerEm
    vals = []
    for c in "מאבגדנסעה":
        if ord(c) not in cm:
            continue
        bp = BoundsPen(gs); gs[cm[ord(c)]].draw(bp)
        if bp.bounds:
            vals.append((bp.bounds[3] - bp.bounds[1]) / em)
    return sum(vals) / len(vals)


def calibrate(chars, alpha, ttf_path):
    """Fit (a) the SDF encoding alpha = SCALE*d + OFFSET and (b) the advance unit, both
    from the SHIPPED glyphs -- so injected letters land on exactly the same scale."""
    xs, ys = [], []
    big = sorted((c for c in chars.items() if c[1][2] > 18 and c[1][3] > 18),
                 key=lambda c: -(c[1][2] * c[1][3]))[:40]
    for _, (x, y, w, h, *_r) in big:
        sub = alpha[int(y):int(y + h), int(x):int(x + w)].astype(float)
        if sub.size < 64:
            continue
        mask = sub >= (sub.max() + sub.min()) / 2.0
        if mask.sum() < 16 or (~mask).sum() < 16:
            continue
        d = signed_distance(mask)
        band = np.abs(d) <= 3.0
        xs.append(d[band]); ys.append(sub[band])
    d = np.concatenate(xs); a = np.concatenate(ys)
    scale, offset = np.polyfit(d, a, 1)
    print(f"  SDF fit over {len(d):,} edge px:  alpha = {scale:.3f}*d + {offset:.2f}   "
          f"(alpha {a.min():.0f}..{a.max():.0f})")

    cap = chars[65][3]
    margin, K = measure_advance_unit(chars)
    print(f"  advance unit: SDF margin={margin:.2f}px  cap={cap:.2f}px  "
          f"K={K:.4f} units/px  (geometric, from the game's own Latin)")
    return float(scale), float(offset), K, cap


# ------------------------------------------------------------------ build
def build(ttf_key="heebo", body_px=None):
    repo = os.path.join(HERE, "..", "..", "..")
    ttf = FONTS[ttf_key]
    if not os.path.isabs(ttf):
        ttf = os.path.join(repo, ttf)
    chars = parse_fnt(os.path.join(OUT, "arabic.fnt"))
    at = Atlas(os.path.join(OUT, "arabic_atlas.xbt"))
    assert (at.w, at.h) == (ATLAS_W, ORIG_H), (at.w, at.h)
    print(f"source: {len(chars)} glyphs, atlas {at.w}x{at.h} R8 mips={at.mips}, "
          f"font={os.path.basename(ttf)}")
    print("calibrating from the game's own glyphs:")
    SCALE, OFFSET, K, cap = calibrate(chars, at.mip0, ttf)

    baseline = chars[65][5] + chars[65][3]
    # Size to MATCH FAR CRY 6 rather than guessing: FC6 draws Hebrew at Heebo's natural em
    # fraction inside Noto Kufi Arabic, i.e. hebrew : arabic-alef = 0.5850 / 0.7598.  FC5's
    # own alef is in the same atlas, so the same ratio reproduces the identical look.
    alef = chars[0x0627][3]
    hb = hebrew_body_em(ttf)
    target = body_px or round(alef * hb / FC6_KUFI_ALEF_EM, 1)
    print(f"  cap={cap:.2f} arabic-alef={alef:.2f} baseline={baseline:.2f}")
    print(f"  FC6 match: heebo body {hb:.4f} em / kufi alef {FC6_KUFI_ALEF_EM:.4f} em "
          f"= {hb/FC6_KUFI_ALEF_EM:.3f}  ->  hebrew body {target} px")

    probe = ImageFont.truetype(ttf, 100)
    b = probe.getbbox("מ")
    px = max(6, int(round(100 * target / (b[3] - b[1]))))
    font = ImageFont.truetype(ttf, px)
    fontSS = ImageFont.truetype(ttf, px * SS)
    ascent = font.getmetrics()[0]
    print(f"  TTF px={px}  ascent={ascent}")

    strip = np.zeros((NEW_H - ORIG_H, ATLAS_W), np.uint8)
    out = dict(chars)
    x = y = row = 0
    a4 = lambda v: (int(v) + 3) & ~3
    for cp in HEBREW:
        if cp in chars:
            continue
        ch = chr(cp)
        bb = font.getbbox(ch)
        gw, gh = bb[2] - bb[0], bb[3] - bb[1]
        adv = font.getlength(ch) * K
        if gw <= 0 or gh <= 0:
            out[cp] = (0, 0, 0, 0, 0, 0, adv); continue
        cw, chh = gw + 2 * MARGIN, gh + 2 * MARGIN
        m = Image.new("L", (cw * SS, chh * SS), 0)
        ImageDraw.Draw(m).text(((MARGIN - bb[0]) * SS, (MARGIN - bb[1]) * SS), ch,
                               fill=255, font=fontSS)
        mask = np.array(m) >= 128
        d = signed_distance(mask) / SS
        d = d[:chh * SS, :cw * SS].reshape(chh, SS, cw, SS).mean(axis=(1, 3))
        if x + cw + PAD4 > ATLAS_W:
            x = 0; y = a4(y + row + PAD4); row = 0
        if y + chh > NEW_H - ORIG_H:
            raise OverflowError(f"no room for U+{cp:04X}")
        strip[y:y + chh, x:x + cw] = np.clip(SCALE * d + OFFSET, 0, 255).astype(np.uint8)
        # the cell overshoots the ink by MARGIN on every side -> pull the offsets back
        out[cp] = (x, ORIG_H + y, cw, chh, bb[0] - MARGIN,
                   baseline - ascent + bb[1] - MARGIN, adv)
        x = a4(x + cw + PAD4); row = max(row, chh)
    added = sum(1 for cp in HEBREW if cp not in chars)
    print(f"  placed {added} hebrew glyphs, rows used {a4(y+row)}/{NEW_H-ORIG_H}")

    with open(os.path.join(OUT, "hebrew.fnt"), "w", encoding="utf-8") as fh:
        fh.write('info face="DIN Mittelschrift LT W1G" size=0 bold=0 italic=0 \n')
        fh.write(f"common lineHeight=0 base=0 scaleW={ATLAS_W} scaleH={NEW_H} pages=1 \n")
        fh.write('page id=0 file="UI\\Common\\fonts\\Fire\\'
                 'DIN_Mittelschrift_LT_W1G_Arabic_1.png"\n')
        fh.write(f"chars count={len(out)}\n")
        # FFDConverter's reader splits on SPACES (tabs -> FormatException).  xadvance is
        # stored quantised at 1/1.3 px and its own 2-decimal export sits just under a step,
        # so snap to the grid and nudge past the boundary -> shipped advances survive exactly.
        for cp in sorted(out):
            cx, cy, cw, chh, xo, yo, adv = out[cp]
            adv = round(adv * ADV_Q) / ADV_Q + 0.0004 if adv > 0 else 0.0
            fh.write(f"char id={cp:<8}x={cx:<9.2f}y={cy:<9.2f}width={cw:<13.2f}"
                     f"height={chh:<14.2f}xoffset={xo:<15.2f}yoffset={yo:<15.2f}"
                     f"xadvance={adv:<16.4f}page=0       chnl=0       \n")

    import json
    json.dump({"sdf_scale": SCALE, "sdf_offset": OFFSET, "adv_units_per_px": K,
               "cap": cap, "body_px": target, "ttf": ttf, "ttf_px": px,
               "atlas": [ATLAS_W, NEW_H], "glyphs": len(out)},
              open(os.path.join(OUT, "hebrew_build.json"), "w"), indent=1)

    mip0 = np.vstack([at.mip0, strip])
    blob, nlev = at.rebuild(mip0)
    open(os.path.join(OUT, "hebrew.xbt"), "wb").write(blob)
    print(f"  wrote hebrew.fnt ({len(out)} glyphs) + hebrew.xbt "
          f"({len(blob):,} B, {ATLAS_W}x{NEW_H}, {nlev} mips)")
    print(f"\n  fnt2ffd dims to enter:  width={ATLAS_W}  height={NEW_H}")

    chk = open(os.path.join(OUT, "hebrew.xbt"), "rb").read()
    a2 = Atlas(os.path.join(OUT, "hebrew.xbt"))
    assert (a2.mip0[:ORIG_H] == at.mip0).all(), "original atlas rows CHANGED"
    print(f"  verify: re-read {a2.w}x{a2.h}, original {ORIG_H} rows byte-identical  OK")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "heebo",
          int(sys.argv[2]) if len(sys.argv) > 2 else None)
