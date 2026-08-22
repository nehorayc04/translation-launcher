"""
WD2 font atlas generator — adds HEBREW glyphs to the game's Arabic font while
keeping every original glyph (Latin / Cyrillic / Arabic) PIXEL- and METRIC-
identical. Hebrew is what lets the Arabic-slot Hebrew text render as real
letters instead of tofu boxes.

Method (preserves vanilla spacing exactly): the original 1024x2048 atlas is
copied verbatim into a taller 1024xH atlas; the original per-glyph metrics are
kept verbatim; only the Hebrew block is rendered (from a TTF, px tuned to match
the original scale) into the new free rows below 2048.

Inputs you must have on disk first (via FFDConverter + the archive extract):
  orig_fnt   = ffd2fnt of the arabic .ffd WITH dims 1024 2048   (real metrics)
  orig_xbt   = the extracted arabic atlas .xbt  (TBX + DXT5 DDS)

  python wd2_font.py <orig_fnt> <orig_xbt> <out_prefix> [ttf]
    -> <out_prefix>.fnt + <out_prefix>.xbt
Then:
  FFDConverter --fnt2ffd -v WD2 -f <arabic.ffd> -b <out_prefix>.fnt -o hebrew.ffd   (dims: 1024 / H)
  wd2_archive.py deploy <font.ffd path> hebrew.ffd   +   deploy <atlas .xbt path> <out_prefix>.xbt
"""
import sys, struct, re, io
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from PIL import Image, ImageFont, ImageDraw

ATLAS_W = 1024
ORIG_H = 2048
EXTRA_H = 512                # room for Hebrew rows; total must stay /4 for DXT5
PX = 30                      # Hebrew is ALL cap-height (no x-height) -> set it well under the
                             # Latin cap so it doesn't tower over the mixed-case Latin
RAISE = 4                    # shift Hebrew UP by this many px (position, not size)
PAD4 = 4                     # >=4px gap so no two glyphs share a DXT5 4x4 block
SS = 8                       # supersample factor for clean SDF distance accuracy (higher = crisper
                             # edges; SS=4 left the Hebrew glyphs softer/fuzzier than the native font)
# The game's font atlas is a SIGNED DISTANCE FIELD in the alpha channel (RGB is
# flat white). Measured from the original Latin glyphs: alpha = 17.29*d + 127.57
# where d = signed distance to the glyph edge in ATLAS px (+inside, -outside).
# The UI shader thresholds alpha~128 for a crisp edge at any scale. Hebrew MUST
# be generated the same way — plain coverage glyphs render fragmented/noisy.
SDF_SCALE = 17.29
SDF_OFFSET = 127.57
SDF_MARGIN = 8              # px of falloff room around the ink (alpha->0 at edge)
# Heebo Medium (clean Hebrew sans) matches the game's Helvetica Neue LT 65 Md
# far better than Arial; only Hebrew glyphs come from it (Latin stays the game's).
HEEBO = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\spiderman2\extracted\_heebo\Heebo-Medium.ttf"
# Hebrew consonants + final forms + niqqud/punctuation
HEBREW = (list(range(0x05D0, 0x05EB)) + list(range(0x0591, 0x05C8))
          + [0x05BE, 0x05C0, 0x05C3, 0x05C6])

_INF = 1e20


def _edt1d(f):
    """Felzenszwalb 1-D squared-distance transform (exact)."""
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
    """Euclidean distance from every cell to the nearest True cell."""
    f = np.where(mask, 0.0, _INF)
    for i in range(f.shape[0]):
        f[i] = _edt1d(f[i])
    for j in range(f.shape[1]):
        f[:, j] = _edt1d(f[:, j].copy())
    return np.sqrt(f)


def sdf_alpha(mask_ss, ss):
    """mask_ss = boolean ink mask at SS resolution. Returns an atlas-resolution
    uint8 alpha array = the game's SDF encoding (clip(SDF_SCALE*d+SDF_OFFSET))."""
    signed = _edt(~mask_ss) - _edt(mask_ss)        # +inside / -outside, in SS px
    signed = signed / ss                            # -> atlas px
    h, w = signed.shape[0] // ss, signed.shape[1] // ss
    signed = signed[:h * ss, :w * ss].reshape(h, ss, w, ss).mean(axis=(1, 3))
    a = np.clip(SDF_SCALE * signed + SDF_OFFSET, 0, 255)
    return a.astype(np.uint8)


def parse_fnt(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in re.finditer(r'char id=(\d+)\s+x=([\d.\-]+)\s+y=([\d.\-]+)\s+width=([\d.\-]+)\s+'
                         r'height=([\d.\-]+)\s+xoffset=([\d.\-]+)\s+yoffset=([\d.\-]+)\s+'
                         r'xadvance=([\d.\-]+)', t):
        cid = int(m.group(1))
        out[cid] = tuple(float(x) for x in m.groups()[1:])   # x,y,w,h,xoff,yoff,xadv
    return out


def build(orig_fnt, orig_xbt, out_prefix, ttf=HEEBO, px=PX):
    existing = parse_fnt(orig_fnt)
    font = ImageFont.truetype(ttf, px)
    # BASELINE alignment (not top-align): place every Hebrew glyph on the SAME
    # baseline as the game's Latin, regardless of px. game baseline (from line
    # top) = A.yoffset + A.height; a glyph's baseline within its rendered cell =
    # font_ascent - bbox_top. So cell yoffset = game_baseline - ascent + bbox_top.
    ascent = font.getmetrics()[0]
    game_baseline = (existing[65][5] + existing[65][3]) if 65 in existing else px * 0.8
    fontSS = ImageFont.truetype(ttf, px * SS)   # hi-res mask for accurate distance
    # MEASURED: Heebo@38 letter advance (20.5) == the game's Latin lowercase advance
    # (20.5), and Heebo space (9) vs Latin space (11). So Hebrew matches Latin with
    # ZERO extra tracking; the old TRACK=11/SPACE_BUMP=12 made Hebrew ~50% wider than
    # English (the in-game "too big" + line clipping). Keep them tiny = equal size.
    TRACK = 7                                    # uniform air added to Heebo's NATURAL (optically-
    SPACE_BUMP = 4                               # kerned) advances. Constant-gap looked optically
    LATIN_TRACK = 0                              # UNEVEN (ו/ע vs מ/ו) — Heebo's own spacing is right.
    M = SDF_MARGIN

    H = ORIG_H + EXTRA_H
    assert H % 4 == 0
    raw = open(orig_xbt, "rb").read()
    # Hebrew goes into a SEPARATE strip (rows 2048..H). The original 2048 rows are
    # kept as PRISTINE DXT5 (spliced below) so Latin stays byte-identical.
    hstrip = Image.new("RGBA", (ATLAS_W, EXTRA_H), (255, 255, 255, 0))

    def a4(v):                                   # round up to a DXT5 4x4 block edge
        return (int(v) + 3) & ~3

    # keep originals' glyphs/metrics, but add a little tracking to Latin LETTERS
    # only (not digits/punct -> no number-display overflow) to relieve crowding.
    chars = {}
    for cid, e in existing.items():
        adv = e[6]
        if (65 <= cid <= 90) or (97 <= cid <= 122) or (0xC0 <= cid <= 0x24F):
            adv += LATIN_TRACK
        chars[cid] = (*e[:6], adv)
    if 32 in chars:                              # widen the word-space for Hebrew
        e = chars[32]; chars[32] = (*e[:6], e[6] + SPACE_BUMP)
    x = 0; sy = 0; row_h = 0; added = 0
    for cp in HEBREW:
        if cp in existing:
            continue
        ch = chr(cp)
        bbox = font.getbbox(ch); adv = font.getlength(ch)
        gw = bbox[2] - bbox[0]; gh = bbox[3] - bbox[1]
        if gw <= 0 or gh <= 0:
            chars[cp] = (0, 0, 0, 0, 0, 0, round(adv) + TRACK); continue
        # SDF: render an ink mask at SS res inside a cell padded by M px (room for
        # the distance falloff), compute the signed-distance alpha the game expects.
        cw, chh = gw + 2 * M, gh + 2 * M
        mimg = Image.new("L", (cw * SS, chh * SS), 0)
        ImageDraw.Draw(mimg).text(((M - bbox[0]) * SS, (M - bbox[1]) * SS),
                                  ch, fill=255, font=fontSS)
        mask = np.array(mimg) >= 128
        alpha = sdf_alpha(mask, SS)              # (chh, cw) uint8
        cell = np.dstack([np.full_like(alpha, 255)] * 3 + [alpha])
        # 4-px aligned placement + >=4px pad so no two glyphs share a DXT5 block
        if x + cw + PAD4 > ATLAS_W:
            x = 0; sy = a4(sy + row_h + PAD4); row_h = 0
        if sy + chh > EXTRA_H:
            raise OverflowError(f"hebrew overflow at cp {cp:#x}; raise EXTRA_H")
        hstrip.paste(Image.fromarray(cell, "RGBA"), (x, sy))
        # the cell extends M px beyond the ink on every side -> shift x/y offsets by
        # -M. spacing is the typographic advance (SDF falloffs may overlap freely).
        yoff = game_baseline - ascent + bbox[1] - M - RAISE   # -RAISE shifts the glyph UP
        # Heebo's NATURAL advance (optically kerned) + uniform TRACK air; natural left bearing.
        chars[cp] = (x, ORIG_H + sy, cw, chh, bbox[0] - M, yoff, round(adv) + TRACK)
        x = a4(x + cw + PAD4); row_h = max(row_h, chh); added += 1

    # write BMFont .fnt
    with open(out_prefix + ".fnt", "w", encoding="utf-8") as f:
        f.write(f'info face="HelveticaNeueLT W1G 65 Md" size={px} bold=0 italic=0 charset="" '
                f'unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1 outline=0\n')
        f.write(f'common lineHeight={px} base={font.getmetrics()[0]} scaleW={ATLAS_W} scaleH={H} '
                f'pages=1 packed=0 alphaChnl=1 redChnl=0 greenChnl=0 blueChnl=0\n')
        f.write('page id=0 file="atlas.png"\n')
        f.write(f'chars count={len(chars)}\n')
        for cp in sorted(chars):
            cx, cy, cw, ch_, xo, yo, adv = chars[cp]
            f.write(f'char id={cp} x={cx:g} y={cy:g} width={cw:g} height={ch_:g} '
                    f'xoffset={xo:g} yoffset={yo:g} xadvance={adv:g} page=0 chnl=15\n')

    # DDS: keep the ORIGINAL DXT5 body (rows 0..2047, pristine Latin) byte-for-byte
    # and append only the freshly-compressed Hebrew strip (rows 2048..H). 2048 is a
    # 4x4 block edge so the block-row stream simply concatenates.
    orig_body = raw[44 + 128: 44 + 128 + ATLAS_W * ORIG_H]
    buf = io.BytesIO(); hstrip.save(buf, format="DDS", pixel_format="DXT5")
    hbody = buf.getvalue()[128:]                  # ATLAS_W*EXTRA_H bytes (128 block-rows)
    assert len(hbody) == ATLAS_W * EXTRA_H, (len(hbody), ATLAS_W * EXTRA_H)
    hdr = bytearray(raw[:44 + 128])              # TBX(44) + original DDS header(128)
    struct.pack_into("<I", hdr, 44 + 4 + 8, H)            # DDS dwHeight
    struct.pack_into("<I", hdr, 44 + 4 + 16, ATLAS_W * H)  # DDS dwPitchOrLinearSize
    open(out_prefix + ".xbt", "wb").write(bytes(hdr) + orig_body + hbody)
    print(f"built {out_prefix}.fnt ({len(chars)} glyphs, +{added} hebrew, px={px}, SS={SS}) + "
          f"{out_prefix}.xbt (atlas {ATLAS_W}x{H}, {len(hdr)+len(orig_body)+len(hbody)} bytes)")
    print(f"  fnt2ffd dims to enter: width={ATLAS_W} height={H}")


if __name__ == "__main__":
    of = sys.argv[1] if len(sys.argv) > 1 else r"c:\tmp\orig_real.fnt"
    ox = sys.argv[2] if len(sys.argv) > 2 else r"c:\tmp\wd2_fonts\ui\fonts\helveticaneuelt_w1g_65_md_arabic_1.xbt"
    out = sys.argv[3] if len(sys.argv) > 3 else r"c:\tmp\heb_font"
    ttf = sys.argv[4] if len(sys.argv) > 4 else HEEBO
    px = int(sys.argv[5]) if len(sys.argv) > 5 else PX
    build(of, ox, out, ttf, px)
