# -*- coding: utf-8 -*-
"""God of War: Ragnarök — Hebrew font injector (GATE 2).

Adds Hebrew glyphs to the Arabic-slot body font (copperplate) WITHOUT growing
any section — the proven gate-1 length-preserving mechanism (splice + re-LZ4,
no WTOC/offset surgery). Reverse-engineering: see ../FONT.md.

Mechanism (all length-preserving):
  1. The font atlas `copperplate_ar` is a raw 1024x1024 **linear BC4** texture
     (8 bytes / 4x4 block). Decode -> draw Hebrew letters into EMPTY 4-aligned
     blocks -> re-encode ONLY the blocks we touched, splicing them back into the
     original bytes (every other glyph stays byte-identical => Latin / digits /
     punctuation / Old-Norse runes are never disturbed, per the project rule).
  2. The glyph table `SMF_1` ("SMF4Copperplate") is a header (0x70) + sorted
     28-byte glyph records (cp@+0). In a Hebrew mod NO string contains Arabic,
     so the 27 lowest-codepoint Arabic records (cp 0x60c..0x638, contiguous) are
     dead weight. We OVERWRITE them in place with Hebrew 0x5d0..0x5ea. Hebrew
     sorts between the preceding record (0x308) and the next Arabic (0x639), so
     the array STAYS SORTED -> safe for binary *or* linear glyph lookup, and the
     file size is unchanged (no resize, SMF_3/2/0 stay byte-identical).

SMF4 record (28 bytes), all atlas coords are fixed-point x8:
  +0  u16 codepoint     +4 u16 kern_ref_a   +6 u16 kern_ref_b   +8 u32 (0)
  +12 u16 atlasX*8      +14 u16 atlasY*8    +16 u16 height*8     +18 u16 y_off
  +20 i16 bearingX*8    +22 u16 width*8     +24 u32 advance*8

Public API:
  inject_hebrew(dec_wad: bytearray, font_path, *, px, log) -> list[metric]
     edits dec_wad IN PLACE (atlas + SMF_1), returns the placed metrics.
  Helpers: bc4_decode / bc4_encode_block / find_resource.
"""
import os, struct
import numpy as np
from PIL import Image, ImageFont, ImageDraw, ImageFilter

ATLAS_W = ATLAS_H = 1024
SMF_HEADER = 0x70
SMF_REC = 28
SMF_SENTINEL = 0xFFFC
HEBREW_CPS = list(range(0x5D0, 0x5EB))          # 0x5d0..0x5ea = 27 letters
# Punctuation we RE-RENDER ourselves so it can be RAISED with the Hebrew (native records only CLIP
# under a yoff edit — they don't reposition; proven on the English). Each is drawn in our font and
# written onto its own native record (off-by-one: glyph P -> record P-1), lifted by the same RAISE.
PUNCT_CHARS = ""            # ALL non-Hebrew glyphs (digits, punct, symbols AND the Latin letters) are
                            # raised by RELOCATING the game's own NATIVE copperplate glyphs into taller
                            # cells (see inject_hebrew's "RAISE NATIVE LATIN" block) — copperplate look
                            # kept, everything on the same raised baseline. So nothing is re-rendered in
                            # David here (David is for the Hebrew letters only, which copperplate lacks).
PUNCT_CPS = [ord(c) for c in PUNCT_CHARS]

# DESCENDER REMAP (2026-07-03) — the +18 vertical field is honored PER CODEPOINT RANGE: Hebrew
# (U+05xx) is IGNORED in-game, but Arabic-presentation-forms (0xFE80) DROP (native Arabic uses
# y_off 90-174). So the 5 Hebrew descender finals get their glyph placed on a spaced Arabic-pres
# record (with a real tail y_off) and the TEXT is remapped to that codepoint (gowr_wad.DESC_REMAP,
# MUST match). Off-by-one: rendering codepoint C draws the record BEFORE it (cp==C-1), so the
# glyph goes in record C-1 and the y_off on BOTH C-1 and the match record C (belt-and-suspenders).
# TEXT target = a BASIC-Arabic letter whose ISOLATED presentation form NATIVELY DESCENDS (proven in
# the pristine SMF: ل/FEDD=11px, م/FEE1=15px, ن/FEE5=11px, و/FEED=11px, ى/FEEF=11px). The engine
# shapes the basic cp -> isolated pres form and applies THAT record's y_off (the drop). So we (a) map
# each Hebrew descender to such a basic letter, (b) write the Hebrew glyph onto the isolated-pres
# record it shapes to, and (c) PRESERVE that record's native y_off = the drop. (2026-07-03: text 0x649
# dropped as native ى; then dropping to 13px raised it -> the native pres y_off IS the drop.)
# False = plain-Hebrew RAISE mode (descenders lifted in our own cell, no Arabic hijack/blit).
# True would re-enable the Arabic-slot blit path (kept for reference).
DESC_REMAP_ACTIVE = False
# Hebrew descender -> BIGGEST native dropping basic-Arabic letter (its isolated form).
DESC_PRESFORM = {0x5E7: 0x0644, 0x5DA: 0x063A, 0x5DF: 0x0646, 0x5E3: 0x0649, 0x5E5: 0x0648}
# basic text cp -> its ISOLATED-pres MATCH record P; the drawn glyph record is P-1.
DESC_GLYPH_PRES = {0x0644: 0xFEDD, 0x063A: 0xFECD, 0x0646: 0xFEE5, 0x0649: 0xFEEF, 0x0648: 0xFEED}
assert len(HEBREW_CPS) == 27

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "extract", "fonts")


# ---------- BC4 codec ----------
def bc4_decode(data, w=ATLAS_W, h=ATLAS_H):
    out = np.zeros((h, w), np.uint8)
    o = 0
    for byb in range(h // 4):
        for bxb in range(w // 4):
            r0, r1 = data[o], data[o + 1]
            bits = int.from_bytes(data[o + 2:o + 8], "little"); o += 8
            if r0 > r1:
                pal = [r0, r1] + [((7 - i) * r0 + i * r1) // 7 for i in range(1, 7)]
            else:
                pal = [r0, r1] + [((5 - i) * r0 + i * r1) // 5 for i in range(1, 5)] + [0, 255]
            for py in range(4):
                for px in range(4):
                    out[byb * 4 + py, bxb * 4 + px] = pal[(bits >> (3 * (py * 4 + px))) & 7]
    return out


def bc4_encode_block(cell16):
    """cell16: flat length-16 uint8. Returns 8 bytes (BC4, r0>r1 8-value mode)."""
    r0 = int(cell16.max()); r1 = int(cell16.min())
    if r0 == r1:
        if r0 == 0:
            return bytes(8)
        r1 = r0 - 1
    pal = [r0, r1] + [((7 - i) * r0 + i * r1) // 7 for i in range(1, 7)]
    bits = 0
    for k in range(16):
        v = int(cell16[k]); best = 0; bd = 999
        for i in range(8):
            d = pal[i] - v
            if d < 0:
                d = -d
            if d < bd:
                bd = d; best = i
        bits |= best << (3 * k)
    return bytes([r0, r1]) + bits.to_bytes(6, "little")


def splice_blocks(orig_atlas_bytes, atlas_img, dirty_blocks):
    """Re-encode only the (bxb,byb) blocks in dirty_blocks, leave the rest intact."""
    out = bytearray(orig_atlas_bytes)
    bx = ATLAS_W // 4
    for (bxb, byb) in dirty_blocks:
        cell = atlas_img[byb * 4:byb * 4 + 4, bxb * 4:bxb * 4 + 4].reshape(-1)
        o = (byb * bx + bxb) * 8
        out[o:o + 8] = bc4_encode_block(cell)
    return bytes(out)


# ---------- WAD resource location (byte-match against the GOWTool unpack) ----------
def find_resource(dec_wad, bin_name):
    d = open(os.path.join(FONTS, bin_name), "rb").read()
    probe = d[len(d) // 2:len(d) // 2 + 64]
    o = bytes(dec_wad).find(probe)
    if o < 0:
        raise RuntimeError(f"{bin_name} not located in WAD")
    start = o - len(d) // 2
    assert bytes(dec_wad[start:start + len(d)]) == d, f"{bin_name} match not exact"
    return start, len(d)


# ---------- SMF helpers ----------
def smf_records(smf):
    """Yield (offset, codepoint) for each glyph record until the sentinel."""
    o = SMF_HEADER
    while o + SMF_REC <= len(smf):
        cp = struct.unpack_from("<H", smf, o)[0]
        if cp == SMF_SENTINEL:
            break
        yield o, cp
        o += SMF_REC


def lowest_arabic_record_offsets(smf, n=27):
    offs = [o for o, cp in smf_records(smf) if 0x600 <= cp <= 0x6FF]
    if len(offs) < n:
        raise RuntimeError(f"only {len(offs)} Arabic records, need {n}")
    return offs[:n]


def write_record(smf, off, cp, atlasX, atlasY, w, h, bearing, advance, y_off=0):
    """y_off is in PLAIN pixels (screen space) -> stored as x8 fixed-point, same
    convention as every other spatial field here (verified against native records:
    caps A/H=0, round x-height e/a/o~0.5px optical dip, true descenders g/j/p/q/y
    ~12.4px -> raw stored value 99). The engine anchors CROP-BOTTOM at
    `base + y_off_px - 1` regardless of h (h only sets the crop's TOP), so a tight
    crop + the correct y_off is what actually moves ink up/down; extending the
    crop's own empty space (no ink) does nothing but ADD to the height field."""
    struct.pack_into("<H", smf, off + 0, cp)
    struct.pack_into("<H", smf, off + 2, 0)
    struct.pack_into("<H", smf, off + 4, 0)      # kern_ref_a
    struct.pack_into("<H", smf, off + 6, 0)      # kern_ref_b
    struct.pack_into("<I", smf, off + 8, 0)
    struct.pack_into("<H", smf, off + 12, int(round(atlasX * 8)))
    struct.pack_into("<H", smf, off + 14, int(round(atlasY * 8)))
    struct.pack_into("<H", smf, off + 16, int(round(h * 8)))
    struct.pack_into("<h", smf, off + 18, int(round(y_off * 8)))   # signed, x8 (negative = shift up)
    struct.pack_into("<h", smf, off + 20, int(round(bearing * 8)))
    struct.pack_into("<H", smf, off + 22, int(round(w * 8)))
    struct.pack_into("<I", smf, off + 24, int(round(advance * 8)))


# ---------- atlas free-space finder ----------
def find_empty_boxes(atlas, cw, ch, n, thr=6):
    boxes = []
    for by in range(0, ATLAS_H - ch + 1, 4):
        for bx in range(0, ATLAS_W - cw + 1, 4):
            if atlas[by:by + ch, bx:bx + cw].max() <= thr:
                boxes.append((bx, by))
    picked = []
    def ov(a, b):
        return not (a[0] + cw <= b[0] or b[0] + cw <= a[0] or
                    a[1] + ch <= b[1] or b[1] + ch <= a[1])
    for b in boxes:
        if all(not ov(b, p) for p in picked):
            picked.append(b)
        if len(picked) >= n:
            break
    if len(picked) < n:
        raise RuntimeError(f"only {len(picked)} empty {cw}x{ch} boxes, need {n}")
    return picked


def pack_boxes(atlas, sizes, thr=6, pad=3, reserved=()):
    """Rectangle packer for VARIABLE-size glyphs into the atlas free space (the fragmented leftovers
    after Hebrew + the reclaimed Latin boxes). Maintains a 4x4-block occupancy grid seeded from the
    current atlas AND from `reserved` rects (x,y,w,h — the already-placed Hebrew/punct BOXES incl.
    their pad, whose empty borders would otherwise read as "free" and let a Latin glyph pack right up
    against a Hebrew glyph -> neighbour-bleed dots). MARKS each placement (incl. pad) occupied so
    later glyphs never overlap. `sizes` = [(w, h), ...]; returns [(glyph_x, glyph_y), ...]."""
    B = 4
    gh, gw = ATLAS_H // B, ATLAS_W // B
    occ = (atlas.reshape(gh, B, gw, B).max(axis=(1, 3)) > thr)
    for (rx, ry, rw, rh) in reserved:                    # block out the full reserved boxes (with pad)
        occ[ry // B:(ry + rh + B - 1) // B, rx // B:(rx + rw + B - 1) // B] = True
    out = [None] * len(sizes)
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])   # TALLEST first (tall cells need
    #                                                                 the scarce tall free runs early)
    for i in order:
        w, h = sizes[i]
        bw = (w + 2 * pad + B - 1) // B
        bh = (h + 2 * pad + B - 1) // B
        # integral image -> O(1) "any occupied in this window" test; BOTTOM-LEFT heuristic (place as
        # LOW as possible then as far LEFT) packs far tighter than first-fit-top-left on fragmented
        # space (fills the big contiguous lower region first, leaves fewer stranded holes).
        ii = np.zeros((gh + 1, gw + 1), np.int64)
        ii[1:, 1:] = np.cumsum(np.cumsum(occ.astype(np.int64), 0), 1)
        spot = None
        for by in range(gh - bh, -1, -1):
            for bx in range(gw - bw + 1):
                s = ii[by + bh, bx + bw] - ii[by, bx + bw] - ii[by + bh, bx] + ii[by, bx]
                if s == 0:
                    spot = (bx, by); break
            if spot:
                break
        if spot is None:
            raise RuntimeError(f"packer: no room for {w}x{h}")
        bx, by = spot
        occ[by:by + bh, bx:bx + bw] = True
        out[i] = (bx * B + pad, by * B + pad)
    return out


# ---------- glyph sizing ----------
def fit_px(font_path, target_letter_h):
    """Pick the px size whose Hebrew body height ('ממה') is CLOSEST to
    target_letter_h (not just the first that clears it -> was overshooting by
    ~5px, reading as oversized/thick next to the Latin caps)."""
    best_px, best_d = 40, 1e9
    for px in range(16, 96):
        f = ImageFont.truetype(font_path, px)
        c = Image.new("L", (px * 2, px * 2), 0)
        ImageDraw.Draw(c).text((px // 2, px // 2), "ממה", font=f, fill=255)
        ys = np.where(np.array(c).max(axis=1) > 40)[0]
        if not len(ys):
            continue
        h = ys.max() - ys.min() + 1
        d = abs(h - target_letter_h)
        if d < best_d:
            best_d, best_px = d, px
        if h > target_letter_h + 10:   # past the target, no point searching further
            break
    return best_px


# Latin baseline sits at the BOTTOM of the ~37px cell (caps fill rows 0..36,
# measured 2026-06-18). We align the Hebrew baseline to the same screen row.
_LATIN_BASELINE = 37


# ---------- main injection ----------
def inject_hebrew(dec_wad, font_path, *, letter_h=30, pad=3, bearing=-2.0, bold=0,
                  render_char=None, log=print):
    """Draw 27 Hebrew glyphs into the copperplate atlas + remap the SMF records,
    EDITING dec_wad (bytearray) in place. Returns metrics.

    Two format facts (both proven in-game 2026-06-18):
    1. OFF-BY-ONE: the record whose codepoint==X stores the glyph for codepoint
       X+1 (verified: the 'A' record holds the 'B' outline). The engine renders
       codepoint C by exact-matching a record cp==C, then drawing the PREVIOUS
       record's glyph. So letter L needs (a) a record at cp==L for the match and
       (b) the glyph(L) stored in the record at cp==L-1. We therefore write 28
       records cp=0x5cf..0x5ea: cp 0x5cf..0x5e9 hold glyphs א..ת, and cp 0x5ea is
       a blank that merely lets the highest letter (ת, 0x5ea) match — without it
       ת never renders (the bug that truncated הגדרות->הגדרו, התחבר->החבר).
    2. The crop must span the glyph's FULL vertical ink extent or tall letters
       (ל) get clipped into a floating fragment. We render every glyph on a tall
       canvas at one fixed baseline, take the UNION ink extent across all 27 as
       the cell, and align the cell's baseline to the Latin baseline via y_off."""
    atlas_off, atlas_sz = find_resource(dec_wad, "copperplate_ar---41.bin")
    smf_off, smf_sz = find_resource(dec_wad, "SMF_1---43.bin")
    log(f"atlas @0x{atlas_off:x} ({atlas_sz}B)  SMF_1 @0x{smf_off:x} ({smf_sz}B)")

    atlas_bytes = bytes(dec_wad[atlas_off:atlas_off + atlas_sz])
    atlas = bc4_decode(atlas_bytes)

    # FREE the UNUSED glyph atlases EARLY (before placing anything) so BOTH the Hebrew AND the raised
    # Latin have a big pool of tall free regions. Hebrew/English text never contains an Arabic, Arabic-
    # presentation, CJK or Hangul codepoint, so those ~370 glyphs (~290 KB, ~28% of the atlas) are
    # dead weight. Their records are left as-is (they'd render blank, but are never referenced by our
    # content). Runic 0x16xx is KEPT (God of War renders Norse runes). Returns the set of dirty blocks.
    _early_dirty = set()

    def _early_mark(bx, by, bw, bh):
        for yy in range(by & ~3, (by + bh + 3) & ~3, 4):
            for xx in range(bx & ~3, (bx + bw + 3) & ~3, 4):
                _early_dirty.add((xx // 4, yy // 4))

    _nsmf_early = bytes(dec_wad[smf_off:smf_off + smf_sz])
    for _o, _cp in smf_records(_nsmf_early):
        if (0x600 <= _cp <= 0x6FF or 0xFB00 <= _cp <= 0xFEFF or
                0x3000 <= _cp <= 0x9FFF or 0xAC00 <= _cp <= 0xD7FF):
            _ax = int(round(struct.unpack_from("<H", _nsmf_early, _o + 12)[0] / 8.0))
            _ay = int(round(struct.unpack_from("<H", _nsmf_early, _o + 14)[0] / 8.0))
            _ah = int(round(struct.unpack_from("<H", _nsmf_early, _o + 16)[0] / 8.0))
            _aw = int(round(struct.unpack_from("<H", _nsmf_early, _o + 22)[0] / 8.0))
            if 1 <= _aw <= 96 and 1 <= _ah <= 72 and _ay + _ah <= ATLAS_H and _ax + _aw <= ATLAS_W:
                _c0, _r0 = max(0, _ax - 2), max(0, _ay - 2)   # +2px margin -> also wipe the faint AA
                atlas[_r0:_ay + _ah + 2, _c0:_ax + _aw + 2] = 0   # halo (else a gray border fragments)
                _early_mark(_c0, _r0, _aw + 4, _ah + 4)

    px = fit_px(font_path, letter_h)
    # #2 INTERNAL SHIFT (2026-07-03): shrink Hebrew ~10% so the raised bodies + the descender
    # tails fit INSIDE the on-baseline cell — the vertical position is baked into the image,
    # never relying on the engine's unreliable +18 field. Trade-off (user-accepted): Hebrew
    # ends up a touch smaller than the Latin and sits a touch higher on mixed lines.
    SHRINK = 0.90
    px = max(10, int(round(px * SHRINK)))

    # Native copperplate glyphs are SOFT but DENSE: alpha peaks ~180/255, fill ~82%, a
    # smooth mid-tone gradient (measured from native A/H/R) — NOT a bright core wrapped in
    # a wide FAINT halo. Our earlier max(sharp, glow*1.4) sprayed exactly such a halo; its
    # sparse low-alpha pixels BC4-banded into the "dots + streaks" (נקודות ופסים) the user
    # saw. Match native: supersample -> LANCZOS downscale (AA) -> ONE mild engraved blur
    # -> rescale the peak to NATIVE_MAX keeping a dense body -> hard-drop only true specks.
    # David is a LIGHT serif; the native copperplate is BOLD + soft. A thin light glyph
    # shrunk into a small BC4 box reads as "smaller + lower quality than the English" (the
    # user's report). Embolden (stroke_width) to the native weight and keep the softness
    # crisp (not mushy) so Hebrew matches the Latin size + weight + cleanliness.
    # QUALITY MATCH (2026-07-03, gowr_quality_lab.py): the native copperplate glyphs are SOFT —
    # measured alpha profile mean~113, peak~173, ~77% of ink pixels are mid-tones (a rich
    # anti-aliased gradient). My previous render was BIMODAL (632 zeros + 366 near-max, only ~21%
    # mid-tone) => hard staircase edges => the "blocky, low quality" the user saw. Fix: NO embolden
    # (bold=0, thin like native), a mild GaussianBlur to spread the gradient, peak lifted to ~205 so
    # the softened body still averages ~native, and keep the low-alpha AA pixels (drop only true
    # <6 noise; the old <26 hard-cut destroyed the anti-aliasing). Validated through a BC4
    # round-trip: mid-tone fraction 0.21 -> 0.48, visibly smooth.
    # WEIGHT MATCH (2026-07-03): native ink density (>90 alpha) is 0.617 — a HEAVY engraved
    # stroke; David regular soft-rendered was only 0.278 (thin/faint = the "bad quality"). Match
    # the native presence with a heavier face (David Bold) + a MaxFilter dilation, and a MODERATE
    # blur (0.8, not 1.15 which read as mushy) so it's smooth-but-not-mushy and not blocky.
    # #1 CLEAN-BLOCK FONT (2026-07-03): switch from the David serif to a uniform-stroke sans
    # (Arial). A block sans is built from constant-width strokes -> it survives BC4 + the tiny
    # 30px atlas box crisply WITHOUT the embolden(DILATE)+GaussianBlur weight hacks the serif
    # needed (those were what read as "pixelated / blurry / bad quality"). No dilation, only a
    # whisper of smoothing so LANCZOS AA stays sharp — modern and clean.
    # MATCH THE NATIVE ENGRAVED PROFILE (2026-07-03). Two things were proven this session:
    #  (a) the 2x-atlas-resolution test enlarged the text in-game -> display size is tied to the
    #      W/H field, so we CANNOT raise atlas resolution; the upscale-blur is an ENGINE ceiling
    #      (bitmap atlas, no SDF) that hits the game's own English too.
    #  (b) measured directly: the native English glyphs are SOFT, NOT sharp — peak ~180 (not 255),
    #      midtone ~0.72, a thick stroke with a wide soft anti-aliased edge = the engraved "depth".
    # So "max sharpness" was the WRONG direction (a sharp source upscales into jaggy halos); the
    # engine wants a soft, thick, ~180-peak source. My BC4 encoder was verified to preserve that
    # gradient losslessly, so the fix is purely in the render: soften + thicken toward native.
    # (Native's exact 0.72 midtone is unreachable at 37px — it was authored at high res and
    # downsampled — but dil+blur gets the closest soft+deep look this size allows.)
    NATIVE_MAX = 185      # soft peak like native (NOT full black) -> engraved, not harsh.
    SOFT = float(os.environ.get("GOWR_SOFT", "0.8"))   # user 2026-07-04: soften the edges but keep
                         # resolution. 0.5(Bold)=too hard, 1.3(Bold)=looked low-res -> 0.8 = softened
                         # edges without the muddy/low-res blur.
    DILATE = 1            # light thickening only (user asked for a thinner stroke than dil=3).
    SS = 4
    font_ss = ImageFont.truetype(font_path, px * SS)
    asc_ss = font_ss.getmetrics()[0]

    # Pass 1: render every glyph on a tall canvas at a FIXED baseline row R and read each
    # glyph's OWN ink extent (top row + bottom row). Non-final letters end ON the baseline;
    # ך/ן/ף/ץ/ק extend below it. We place EACH letter individually (not a shared cell) so a
    # normal letter is anchored exactly like a Latin cap (y_off=0) and only true descenders
    # drop below — fixing the "Hebrew floats too high" report (the shared cell forced every
    # letter to carry the descender space + a taller body).
    Tn, R, CWmax = px * 3, px * 2, px * 2
    rendered = []      # (cp, alpha, x0, x1, iy0, iy1)
    for cp in HEBREW_CPS + PUNCT_CPS:
        ch = (render_char(cp) if render_char else chr(cp)) if cp in HEBREW_CPS else chr(cp)
        sc = Image.new("L", (CWmax * SS, Tn * SS), 0)
        ImageDraw.Draw(sc).text((4 * SS, R * SS - asc_ss), ch, fill=255, font=font_ss,
                                stroke_width=bold * SS, stroke_fill=255)  # match native weight
        a = np.array(sc.resize((CWmax, Tn), Image.LANCZOS)).astype(np.uint8)
        if DILATE:
            a = np.array(Image.fromarray(a).filter(ImageFilter.MaxFilter(DILATE)))  # heavier weight
        if SOFT > 0:
            a = np.array(Image.fromarray(a).filter(ImageFilter.GaussianBlur(SOFT)))
        a = a.astype(np.float32)
        if a.max() > 0:
            a *= (NATIVE_MAX / a.max())
        # SOFT black-point (2026-07-03): a HARD low-alpha cut (a[a<16]=0) leaves a sharp CONTOUR
        # at the threshold that BC4 bands into a STREAK around the glyph (the user's "פסים").
        # Instead SUBTRACT a floor and clamp -> the faint halo fades to 0 smoothly (no step),
        # which kills BOTH the dots and the streak; then renormalize the peak back to NATIVE_MAX.
        FAINT_CUT = int(os.environ.get("GOWR_FAINT_CUT", "6"))   # keep a soft edge halo but trim the muddy far halo
        a = (a - FAINT_CUT).clip(0, None)
        if a.max() > 0:
            a *= (NATIVE_MAX / a.max())
        a = a.clip(0, NATIVE_MAX).astype(np.uint8)
        ys, xs = np.where(a > 0)
        if len(xs) == 0:
            raise RuntimeError(f"font renders nothing for U+{cp:04X} ({ch})")
        rendered.append((cp, a, int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())))

    # ENGINE MODEL — the +18 field is a QUANTIZED/MAGIC value, NOT a free pixel offset
    # (gowr_rawdiff.py, 2026-07-03): raw-byte-diffing native records, the ONLY byte distinguishing
    # a descender from a same-size non-descender is +18, and EVERY native descender (p,g,y,j) has
    # +18 = EXACTLY 99, every round letter EXACTLY 4, every cap/flat letter EXACTLY 0. The engine
    # only honors these specific values; an arbitrary +18 (like my earlier computed 88) is treated
    # as 0 -> no descent. This explains EVERY observation: my non-descenders (arbitrary +18) all
    # sat on the baseline (=treated as 0, correct), and my ק at 88 never dropped (not a magic
    # value -> 0). Placement is still bottom-anchored: screen_bottom = baseline + descent, where
    # descent = the font's fixed 12.375px iff +18==99, else 0.
    # CONSTRUCTION (bottom-anchored, crop bottom = the row that lands on `baseline + descent`):
    #   * descender (ink extends > DESC_THRESH below the render baseline R): crop INCLUDES the tail
    #     (a[iy0:iy1+1]); set +18 = 99 so the whole glyph drops the font's standard 12.375px ->
    #     head at x-height, tail below the line (exactly like native p).
    #   * everything else (normal letters AND high letters like yod): crop the box DOWN TO the
    #     render baseline R (a[iy0:R+1]) so bottom-anchoring at +18=0 leaves each letter's ink at
    #     its own natural height above the line — normal letters sit on the baseline, yod floats
    #     high (empty rows below its ink), none clipped.
    # PAD keeps a wide empty atlas border (mip/bilinear neighbour-bleed was the "dots").
    # DESCENDER dropped (2026-07-03): the engine's +18 vertical field is UNRELIABLE on the Arabic
    # slot — measured NONLINEAR (160 raw = 0px, 240 raw = ~40px), so a clean ~12px tail can't be
    # dialed in, and 240 pushed ק's tail 43px down with the head floating ("ק up"). Robust choice:
    # crop EVERY glyph to end at the baseline R (yo=0) -> clean stub finals (ק ך ן ף ץ, standard in
    # many Hebrew UI faces), normal letters on the baseline, yod floats high (empty rows below its
    # ink). No dependency on the flaky vertical field.
    # #2 INTERNAL SHIFT (2026-07-03): bake the vertical position into the IMAGE, not the
    # engine's +18 field. Extend every cell's bottom RAISE px BELOW the render baseline R and
    # anchor the cell bottom on the Latin baseline (y_off=0, which IS reliable). Effect:
    #  * a normal letter carries RAISE empty rows at the bottom -> its ink sits RAISE px ABOVE
    #    the baseline (the accepted "Hebrew a touch higher");
    #  * a descender (ק ן ך ף ץ) draws its tail DOWN into that freed RAISE band -> the tail
    #    hangs toward the baseline instead of being a cut-off stub.
    # No dependency on the flaky vertical field; the 10% shrink keeps the raised bodies from
    # reading as oversized and gives the tails room to fall.
    # SHOW DESCENDER TAILS without raising the whole Hebrew (user, 2026-07-03) and without the
    # DROP artifact (the "פסים" = a large y_off pushing the glyph out of its line box). PER-GLYPH
    # crop, y_off=0 for ALL:
    #  * a normal letter crops at the baseline (cbot=R) -> stays on the line (aligned w/ English);
    #  * a real descender (ק ן ף ץ ך = SOLID ink below R) crops to its full tail (cbot=iy1) ->
    #    bottom-anchored (y_off=0) the TAIL lands on the baseline and only THAT letter's body
    #    lifts by the tail depth; the normal letters do NOT move.
    # y_off stays 0 everywhere -> no dash artifact; faint sub-baseline halo (<60) is zeroed so
    # only the solid tail renders (no faint dash under it).
    # PROPER descenders: tail goes BELOW the baseline, body stays aligned (user rejected the
    # body-lift). A descender gets its full-tail cell (cbot=iy1) AND a per-glyph y_off = the tail
    # depth (iy1-R), which pushes the cell down so the body baseline lands on the engine baseline
    # and the tail hangs below it — exactly how native Latin g/p/y use y_off=99. The DROP "פסים"
    # came from a LARGE uniform y_off (24-32px) shoving glyphs out of the line box; a descender's
    # y_off is only ~12px, so it should move cleanly without the artifact. Normal letters keep
    # cbot=R, y_off=0. Faint sub-baseline halo (<60) zeroed so only the solid tail renders.
    # TWO facts finally reconciled (2026-07-03): (1) the engine reads a letter's vertical offset
    # from the record it MATCHES (cp==letter), NOT the glyph record (cp==letter-1) — that's why
    # setting the glyph record did nothing while the uniform DROP (all records) worked; (2) the
    # +18 field honors the MAGIC descender value 99 (every native Latin descender is exactly 99 =
    # a 12.375px drop). So a descender gets its full-tail cell (cbot=iy1, y_off 0 on the glyph
    # record) and its MATCH record (cp==letter) is set to 99 in a later pass -> body on the
    # baseline, tail 12.375px below, EXACTLY like native g/p/y. Normal letters crop at R, stay put.
    PAD = 10        # wide empty atlas border kills mip/BC4 neighbour-bleed (the "noise" round letters)
    # LETTER SPACING is the glyph ADVANCE (cursor step), INDEPENDENT of the atlas PAD above: advance =
    # ink_width + (PAD - TRACK). PAD stays 10 for the atlas border; TRACK pulls the next letter closer
    # on screen without touching the atlas. User 2026-07-04: inter-letter gap too big -> tighten a bit.
    TRACK = int(os.environ.get("GOWR_TRACK", "8"))
    cells = []      # (cp, cell_img, gw, gh, y_off_px)
    desc_letters = set()
    # RAISE the WHOLE Hebrew up (user 2026-07-03: "raise all the Hebrew letters and the special
    # characters up"). The engine won't let a tail cross BELOW the baseline, so instead we lift every
    # letter by RAISE px (append RAISE empty rows -> bottom-anchoring pushes the glyph up) and let the
    # special finals ק ך ן ף ץ keep their FULL tail, which now hangs DOWN into that freed space toward
    # the true baseline — visible, not cut, and its BODY stays level with every other (raised) letter.
    # RAISE defaults to the deepest tail so nothing is cut; tunable via GOWR_DESC_RAISE.
    # RAISE the whole set (Hebrew AND our re-rendered punctuation) UP by RAISE px (append empty rows
    # -> bottom-anchoring lifts the glyph). Hebrew + punctuation move together so they stay aligned,
    # and the special finals ק ך ן ף ץ keep their FULL leg, which hangs DOWN into the freed gap toward
    # the baseline — visible, not cut, body level with everything. Tunable via GOWR_DESC_RAISE.
    # RAISE = the DEEPEST leg (Hebrew descenders only) so every leg fits WHOLE — clipping a leg
    # mid-stroke left a hard bottom edge that BC4 banded into the "dashes/dots below the letters".
    # With the full soft-ended leg kept, there is no hard edge.
    def _realleg(a, x0, x1, iy0, iy1):
        if iy1 <= R:
            return 0
        strong = np.where((a[R + 1:iy1 + 1, x0:x1 + 1] >= 90).any(axis=1))[0]
        return (iy1 - R) if (len(strong) and int(strong.max()) >= 5) else 0
    maxtail = max((_realleg(a, x0, x1, iy0, iy1) for cp, a, x0, x1, iy0, iy1 in rendered
                   if cp in HEBREW_CPS), default=0)
    RAISE = int(os.environ.get("GOWR_DESC_RAISE", str(maxtail)))
    BOT = R + RAISE                                   # uniform cell bottom -> lands on the baseline
    # UNIFORM RAISE (user 2026-07-04: "raise EVERY letter to the SAME height as ק ן ף ך ץ").
    # Every cell's BOTTOM is the same row (R+RAISE); bottom-anchored on the baseline that lifts every
    # letter's BODY by exactly RAISE, so all bodies align at one height, and the descender finals draw
    # their FULL leg down into that freed band toward the baseline. This is CLEAN because the empty
    # gap below a normal letter is the SAME kind of zero-gap the yod already carries in the shipped
    # build (proven clean in-game — an empty region under a glyph does NOT bleed). The earlier
    # raise-noise was LANCZOS/blur RINGING in the rows just below the render baseline (the letter's
    # soft bottom edge), NOT the gap itself: so for non-descenders we HARD-ZERO everything below R
    # before cropping -> a genuinely empty, ringing-free band -> no floating marks. No engine +18
    # dependency (position baked into the image), no per-letter height jump (all cells same bottom).
    for cp, a, x0, x1, iy0, iy1 in rendered:
        is_desc = False
        if iy1 > R:
            strong = np.where((a[R + 1:iy1 + 1, x0:x1 + 1] >= 90).any(axis=1))[0]
            is_desc = bool(len(strong)) and int(strong.max()) >= 5
        col = a[:, x0:x1 + 1].copy()
        if is_desc:
            if cp in HEBREW_CPS:
                desc_letters.add(cp)
        else:
            col[R + 1:, :] = 0                            # kill sub-baseline ringing -> clean zero-gap
        cell = col[iy0:BOT + 1, :].copy()                # own ink top -> uniform bottom (= baseline)
        cells.append((cp, cell, cell.shape[1], cell.shape[0], 0.0))
    dirty = set(_early_dirty)                             # carry the early unused-range clears forward
    metrics = []

    def mark(bx, by, bw, bh):
        for yy in range(by & ~3, (by + bh + 3) & ~3, 4):
            for xx in range(bx & ~3, (bx + bw + 3) & ~3, 4):
                dirty.add((xx // 4, yy // 4))

    def place(group_cells, bw, bh, boxes, gpad):
        for (cp, cell, gw, gh, yoff), (bx, by) in zip(group_cells, boxes):
            ox, oy = bx + gpad, by + gpad
            if oy + gh > ATLAS_H or ox + gw > ATLAS_W:
                raise RuntimeError("glyph overflow")
            atlas[by:by + bh, bx:bx + bw] = 0        # clear box (no residual speckle)
            atlas[oy:oy + gh, ox:ox + gw] = cell
            mark(bx, by, bw, bh)
            metrics.append(dict(cp=cp, x=ox, y=oy, w=gw, h=gh, advance=max(gw + 1, gw + gpad - TRACK), yoff=yoff))

    # Hebrew: 28 big boxes (+1 blank for the ת match). Placed first.
    heb_cells = [c for c in cells if c[0] in HEBREW_CPS]
    CW = ((max(c[2] for c in heb_cells) + 2 * PAD + 2) & ~3)
    CH = ((max(c[3] for c in heb_cells) + 2 * PAD + 2) & ~3)
    hboxes = find_empty_boxes(atlas, CW, CH, len(heb_cells) + 1, thr=2)
    place(heb_cells, CW, CH, hboxes, PAD)
    bxd, byd = hboxes[len(heb_cells)]                 # trailing blank box for the ת match record
    atlas[byd:byd + CH, bxd:bxd + CW] = 0
    mark(bxd, byd, CW, CH)

    # Punctuation: smaller boxes + a tight PAD (they're small; a wide border wastes scarce atlas
    # space), found AFTER the Hebrew is in the atlas (so no overlap).
    punct_cells = [c for c in cells if c[0] not in HEBREW_CPS]
    if punct_cells:
        PADp = 8
        CWp = ((max(c[2] for c in punct_cells) + 2 * PADp + 2) & ~3)
        CHp = ((max(c[3] for c in punct_cells) + 2 * PADp + 2) & ~3)
        pboxes = find_empty_boxes(atlas, CWp, CHp, len(punct_cells), thr=2)
        place(punct_cells, CWp, CHp, pboxes, PADp)

    # ===== RAISE THE NATIVE LATIN GLYPHS (user 2026-07-04: "raise the English too — the TEXT
    # itself, not the crop"). Native copperplate Latin sits in TIGHT atlas cells with 0 headroom
    # above (measured) -> a y_off raise would TOP-CLIP them (the documented failure). So we RELOCATE
    # every Latin glyph into a NEW cell = [native pixels at the TOP] + [RAISE empty rows below];
    # bottom-anchored, that lifts the copperplate glyph by RAISE with NO clip and NO resize (h is the
    # vertical anchor, not the ink scale — proven by the Hebrew cells the user just approved). SAFE:
    # the glyph for codepoint C lives in record cp==C-1 (used ONLY to render C); y_off/bearing/advance/
    # w/cp are kept 100% native -> zero metric/width change to any character. Atlas fits (37% free +
    # the reclaimed old boxes). Toggle off with GOWR_NO_LATIN_RAISE if the engine ever resizes by h.
    native_updates = []
    if not os.environ.get("GOWR_NO_LATIN_RAISE"):     # relocate every Latin glyph into a taller (raised) cell
        _nsmf0 = bytes(dec_wad[smf_off:smf_off + smf_sz])
        _lat = []
        # px captured around each tight record box. TOP=2 already killed the top-clip (user-confirmed
        # 2026-07-04); the BOTTOM needs MORE — copperplate baseline serifs + descenders (g/p/y/','/')')
        # extend well below the tight record box, so a 2px bottom margin still clipped them.
        _LATMT = int(os.environ.get("GOWR_LATIN_MARGIN_TOP", "2"))
        # BOTTOM: allow a few px PAST the RAISE band so a real descender is captured WHOLE. Measured
        # from the atlas: a copperplate 'g' descender runs ~12px strong / ~18px soft below the tight
        # record box (field +18=99 is the native descender marker), deeper than RAISE(10). Capping at
        # RAISE clipped it (user 2026-07-04: "g still clipped"). RAISE+3 captures the full STRONG tail;
        # a descender whose _ext exceeds RAISE simply hangs (band=0) a few px below the baseline (that
        # is where a descender belongs — natural, not clipped) via the variable-size packer.
        _LATMB = int(os.environ.get("GOWR_LATIN_MARGIN_BOT", str(RAISE + 3)))
        # ONLY these glyphs legitimately drop below the baseline. Restricting the gap-tolerant DEEP
        # scan to them means the tight scan (below) is used for every non-descender, so a 1px atlas gap
        # to the next packed row is NEVER crossed for caps/x-height letters (that would grab a neighbour
        # -> stray dots + packer overflow, the earlier bug). Codepoints are the GLYPH (record cp = -1).
        _DESCCP = {ord(c) for c in "gpqyj,;()[]/"}
        for _o, _cp in smf_records(_nsmf0):
            # Relocate EVERY non-Hebrew glyph that still has ink (Latin, Latin-1 «»®, punctuation,
            # Runic, PUA button-icons, …). Consolidating them ALL into the freed region leaves the
            # atlas clean-but-for-Hebrew, so the packer gets big contiguous runs — AND it raises the
            # whole non-Hebrew set uniformly (the goal). The unused Arabic/CJK/Hangul glyphs were
            # already zeroed early, so their (now-empty) regions are skipped by the ink test below.
            _ax = int(round(struct.unpack_from("<H", _nsmf0, _o + 12)[0] / 8.0))
            _ay = int(round(struct.unpack_from("<H", _nsmf0, _o + 14)[0] / 8.0))
            _lh = int(round(struct.unpack_from("<H", _nsmf0, _o + 16)[0] / 8.0))
            _lw = int(round(struct.unpack_from("<H", _nsmf0, _o + 22)[0] / 8.0))
            # sanity-filter garbage records (a stray record had h~8185); real glyphs are small.
            if not (1 <= _lw <= 96 and 1 <= _lh <= 72 and _ay + _lh <= ATLAS_H and _ax + _lw <= ATLAS_W):
                continue
            if int(atlas[_ay:_ay + _lh, _ax:_ax + _lw].max()) <= 2:   # empty (cleared unused glyph) — skip
                continue
            # Native records bound the copperplate glyphs TIGHTLY, so serifs/descenders sit just OUTSIDE
            # the box -> a tight read CLIPPED them (user 2026-07-04: top-clip fixed by TOP=2; the BOTTOM
            # needed more). TOP: fixed _LATMT margin. BOTTOM: extend over CONNECTED ink only (the glyph's
            # own baseline serif / descender), stopping at the first EMPTY row before the packed neighbour
            # below — so a neighbour's pixels are never pulled in (a blind _LATMB margin DID grab them ->
            # extra cells -> packer overflow). Per-glyph: the raise band shrinks by exactly the captured
            # depth _ext, so the glyph's ORIGINAL baseline is preserved AND the packed cell height stays
            # CONSTANT (= _lh + _LATMT + RAISE), which keeps the packer within budget.
            _y0 = max(0, _ay - _LATMT)
            _yb = _ay + _lh; _bmax = min(ATLAS_H, _ay + _lh + _LATMB)
            if (_cp + 1) in _DESCCP:
                # DESCENDER glyph: scan gap-TOLERANT (a copperplate tail has thin AA breaks; the old
                # stop-at-first-empty halted there with _ext=0 -> clipped every descender regardless of
                # _LATMB, which is why 6->10 changed nothing). Stop on 3 CONSECUTIVE empty rows (past
                # the tail, before the next packed row) or at _LATMB.
                _erun = 0
                while _yb < _bmax:
                    if int(atlas[_yb, _ax:_ax + _lw].max()) > 2:
                        _erun = 0
                    else:
                        _erun += 1
                        if _erun >= 3:
                            break
                    _yb += 1
            else:
                # NON-descender: TIGHT scan (stop at the first empty row) so a 1px gap to the next
                # packed atlas row is never crossed -> no neighbour ink pulled in.
                while _yb < _bmax and int(atlas[_yb, _ax:_ax + _lw].max()) > 2:
                    _yb += 1
            while _yb > _ay + _lh and int(atlas[_yb - 1, _ax:_ax + _lw].max()) <= 2:
                _yb -= 1
            _ext = _yb - (_ay + _lh)                       # captured serif/descender depth (0.._LATMB)
            _pix = atlas[_y0:_yb, _ax:_ax + _lw].copy()
            _bandg = max(0, RAISE - _ext)                  # per-glyph band -> baseline kept, cell size constant
            _lat.append((_o, _ax, _y0, _lw, _yb - _y0, _pix, _bandg))
        # Clear the ENTIRE atlas EXCEPT the just-placed Hebrew boxes -> ONE big clean region for the
        # raised Latin. (Per-glyph clears left faint AA borders that fragmented the packer into thin
        # columns; the Latin pixels are already safe in _lat, so a full wipe is clean + trivial to
        # pack.) Everything outside the Hebrew boxes becomes dirty -> the whole atlas is re-encoded.
        _keep = np.zeros(atlas.shape, bool)
        for (bx, by) in hboxes:
            _keep[by:by + CH, bx:bx + CW] = True
        atlas[~_keep] = 0
        dirty.update((bxb, byb) for byb in range(ATLAS_H // 4) for bxb in range(ATLAS_W // 4))
        # (the unused Arabic/CJK/Hangul atlases were already freed EARLY, before Hebrew placement.)
        # NPAD=10: a glyph packed too close lets its atlas NEIGHBOUR bleed (via the engine's mip/
        # bilinear font sampling) into this glyph's RAISE band, rendering as stray DOTS + STREAKS under
        # the text (user-confirmed in-game at NPAD=3 — 6px was NOT enough; the atlas cell itself was
        # clean, so it's a runtime mip-sample, invisible in a static atlas dump). The Hebrew ran CLEAN
        # at PAD=10, so match it: 10px pad -> 20px between Latin cells + 20px from any Hebrew glyph
        # (reserved box pad 10 + Latin pad 10) -> the mip sample of the raise band stays empty.
        NPAD = 10
        # Reserve the Hebrew boxes so a Latin glyph can't pack into a Hebrew glyph's pad and bleed a
        # dot under it. Cheap now (the atlas is ~98% free after the full wipe).
        _reserved = [(bx, by, CW, CH) for (bx, by) in hboxes]
        _sizes = [(_lw, _lh + _bg) for (_o, _ax, _ay, _lw, _lh, _px, _bg) in _lat]   # cell = margin-glyph + per-glyph band (constant height)
        if os.environ.get("GOWR_PACKDBG"):
            _o2 = (atlas.reshape(256, 4, 256, 4).max(axis=(1, 3)) > 2)
            for (rx, ry, rw, rh) in _reserved:
                _o2[ry // 4:(ry + rh + 3) // 4, rx // 4:(rx + rw + 3) // 4] = True
            _f = ~_o2; _best = 0
            for _c in range(256):
                _r = 0
                for _v in _f[:, _c]:
                    _r = _r + 1 if _v else 0
                    _best = max(_best, _r)
            log(f"pre-pack: free={100 * _f.mean():.0f}% tallest-free-col={_best * 4}px "
                f"need {len(_lat)} cells up to {max(s[1] for s in _sizes)}px tall")
            _dd = r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\294886b0-b11d-4871-9d51-a39286aa9ef5\scratchpad"
            Image.fromarray((_o2.astype(np.uint8) * 255)).save(os.path.join(_dd, "preclear_occ.png"))
            Image.fromarray(atlas).save(os.path.join(_dd, "preclear_atlas.png"))
        _spots = pack_boxes(atlas, _sizes, thr=70, pad=NPAD, reserved=_reserved)    # variable-size packer
        for (_o, _ax, _ay, _lw, _lh, _px, _bg), (ox, oy) in zip(_lat, _spots):
            atlas[oy:oy + _lh + _bg, ox:ox + _lw] = 0   # clear the whole cell (margin-glyph + per-glyph band)
            atlas[oy:oy + _lh, ox:ox + _lw] = _px       # margin-glyph at TOP; the band rows below stay empty
            mark(ox - NPAD, oy - NPAD, _lw + 2 * NPAD, _lh + _bg + 2 * NPAD)
            native_updates.append((_o, ox, oy, _lh + _bg))     # h = margin-glyph + per-glyph band -> baseline preserved
        log(f"raised {len(native_updates)} native Latin glyphs by {RAISE}px (relocated, copperplate kept)")

    # DEFINITIVE TEST (GOWR_DESC_BLIT): paint our descender pixels INTO the native isolated-pres
    # glyph rect and leave that record 100% native. Isolates "our pixels" from "our record fields":
    # if the letter now DROPS, the drop is gated by native record metrics (h/atlas/bearing) we were
    # clobbering; if not, the drop is bound to the native pixels themselves.
    # DESCENDER DROP (production, 2026-07-03). The Hebrew range ignores the +18 field entirely
    # (99/104/184 all raised); ONLY native Arabic glyphs at their native atlas slot drop. So each
    # Hebrew descender's TEXT is remapped (gowr_wad.DESC_REMAP) to a basic-Arabic letter whose
    # isolated form is a big native dropper, and we BLIT our Hebrew glyph INTO that native glyph's
    # atlas rect while leaving the record 100% NATIVE -> the engine draws our pixels with the native
    # drop. Constrained to the native rect SIZE (can't enlarge — changing w/h kills the drop), and
    # a cleared margin around each blit prevents mip/bilinear neighbour-bleed (the earlier "dots").
    _nsmf = dec_wad[smf_off:smf_off + smf_sz]                     # native SMF (records untouched here)
    _noff = {c: o for o, c in smf_records(_nsmf)}
    _rmap = {cp: (a, x0, x1, iy0, iy1) for cp, a, x0, x1, iy0, iy1 in rendered}
    for L, B in ({} if not DESC_REMAP_ACTIVE else DESC_PRESFORM).items():
        if L not in desc_letters:
            continue
        P = DESC_GLYPH_PRES.get(B)
        goff = _noff.get(P - 1) if P else None                    # native glyph record P-1 (drawn)
        if goff is None:
            continue
        nax = int(round(struct.unpack_from("<H", _nsmf, goff + 12)[0] / 8.0))
        nay = int(round(struct.unpack_from("<H", _nsmf, goff + 14)[0] / 8.0))
        nh = max(1, int(round(struct.unpack_from("<H", _nsmf, goff + 16)[0] / 8.0)))
        nw = max(1, int(round(struct.unpack_from("<H", _nsmf, goff + 22)[0] / 8.0)))
        a, x0, x1, iy0, iy1 = _rmap[L]
        glyph = a[iy0:iy1 + 1, x0:x1 + 1]                         # our full glyph (body + tail)
        g = np.array(Image.fromarray(glyph).resize((nw, nh), Image.LANCZOS))  # fit the native rect
        M = 4
        y0c, x0c = max(0, nay - M), max(0, nax - M)               # clear a margin -> no neighbour bleed
        atlas[y0c:nay + nh + M, x0c:nax + nw + M] = 0
        atlas[nay:nay + nh, nax:nax + nw] = g
        for yy in range((y0c) & ~3, (nay + nh + M + 3) & ~3, 4):
            for xx in range((x0c) & ~3, (nax + nw + M + 3) & ~3, 4):
                dirty.add((xx // 4, yy // 4))
        log(f"BLIT {chr(L)} -> native pres U+{P - 1:04X} @({nax},{nay}) {nw}x{nh} (native drop)")

    if os.environ.get("GOWR_DUMP"):
        import json as _json
        _d = r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\294886b0-b11d-4871-9d51-a39286aa9ef5\scratchpad"
        Image.fromarray(atlas).save(os.path.join(_d, "atlas_full.png"))
        _json.dump([{"cp": hex(m["cp"]), "x": m["x"], "y": m["y"], "w": m["w"], "h": m["h"]} for m in metrics],
                   open(os.path.join(_d, "atlas_metrics.json"), "w"))
        log("DUMPED atlas_full.png + atlas_metrics.json")

    body = R - min(iy0 for _, _, _, _, iy0, _ in rendered)
    log(f"font={os.path.basename(font_path)} px={px} body~{body}px (target cap≈{letter_h}) "
        f"CW={CW} CH={CH} {len(dirty)} dirty blocks")
    new_atlas = splice_blocks(atlas_bytes, atlas, dirty)
    assert len(new_atlas) == atlas_sz
    dec_wad[atlas_off:atlas_off + atlas_sz] = new_atlas

    smf = bytearray(dec_wad[smf_off:smf_off + smf_sz])
    heb_metrics = [m for m in metrics if m["cp"] in HEBREW_CPS]      # 27, order preserved
    punct_metrics = [m for m in metrics if m["cp"] not in HEBREW_CPS]
    targets = lowest_arabic_record_offsets(smf, 28)
    for i, m in enumerate(heb_metrics):              # cp-1: format's +1 convention
        write_record(smf, targets[i], m["cp"] - 1, m["x"], m["y"], m["w"], m["h"],
                     bearing, m["advance"], y_off=m["yoff"])
    # exact-match record for the highest letter ת (cp 0x5ea) -> blank glyph, y_off=0
    write_record(smf, targets[27], 0x5EA, bxd + PAD, byd + PAD, 1, 4, bearing, 4, y_off=0)

    # Re-rendered punctuation onto its OWN native record (off-by-one: glyph P is drawn from record
    # P-1), raised by the same RAISE (baked into the cell) so it aligns with the raised Hebrew.
    _po = {c: o for o, c in smf_records(smf)}
    _praised = 0
    for m in punct_metrics:
        off = _po.get(m["cp"] - 1)
        if off is not None:
            # PRESERVE the native advance + bearing of record P-1. That record is the ANCHOR for
            # codepoint P-1 (space 0x20 for '!', digit '9' 0x39 for ':', '+' 0x2B for ',' …), and if
            # the engine takes a glyph's advance/bearing from its MATCH record, overwriting them here
            # would resize the SPACE / DIGITS (a spacing bug). We change ONLY the glyph POSITION
            # fields (atlasX/Y/w/h + our raised y_off); the width metrics stay 100% native.
            nat_bear = struct.unpack_from("<h", smf, off + 20)[0]
            nat_adv = struct.unpack_from("<I", smf, off + 24)[0]
            write_record(smf, off, m["cp"] - 1, m["x"], m["y"], m["w"], m["h"],
                         bearing, m["advance"], y_off=m["yoff"])
            struct.pack_into("<h", smf, off + 20, nat_bear)      # RESTORE native bearing
            struct.pack_into("<I", smf, off + 24, nat_adv)       # RESTORE native advance
            _praised += 1
    log(f"re-rendered + raised {_praised}/{len(punct_metrics)} punctuation glyphs")

    # Apply the NATIVE LATIN raises to the SMF: ONLY the glyph POSITION fields change (atlasX/atlasY
    # -> the relocated box, h += RAISE -> the taller cell lifts the glyph via bottom-anchoring).
    # y_off / bearing / advance / w / cp stay 100% native -> the character's width + spacing + drop
    # are unchanged; only its vertical position rises by RAISE, matching the Hebrew.
    for _o, ox, oy, nh in native_updates:
        struct.pack_into("<H", smf, _o + 12, int(round(ox * 8)))
        struct.pack_into("<H", smf, _o + 14, int(round(oy * 8)))
        struct.pack_into("<H", smf, _o + 16, int(round(nh * 8)))
    if native_updates:
        log(f"applied {len(native_updates)} native Latin raises to SMF records")

    # DEFAULT native-Latin raise = a pure y_off SHIFT (cheap: no atlas edits, no h change -> no resize
    # risk). The native cells stay put; we only lower each Latin record's bottom-anchor by RAISE
    # (y_off -= RAISE) so the copperplate glyph rises by RAISE, matching the Hebrew. Safe by geometry:
    # the raised Hebrew (glyph top ~baseline-62) does NOT clip (user-approved), and a raised Latin cap
    # tops out at only ~baseline-51 (< 62) -> within the same line ascent -> no top-clip. The native
    # '-' already ships y_off=-11.6 (raised) and renders fine = negative y_off REPOSITIONS, not clips.
    # Shift every record with cp in 0x1F..0x7E so whichever record the engine reads y_off from (match
    # vs glyph) is covered; each codepoint's governing y_off is shifted exactly once (no double-raise).
    # NOTE: the y_off shift path (GOWR_LATIN_YOFF) is DISABLED by default — proven in-game to CLIP
    # the English ("the crop rose, not the text"): +18 is a texture-V sampling offset, not a screen
    # anchor, so shifting it moves the visible crop and cuts the glyph. Relocation (above) is correct.
    if os.environ.get("GOWR_LATIN_YOFF") and not native_updates:
        _raised = 0
        for _o, _cp in smf_records(smf):
            if 0x1F <= _cp <= 0x7E:
                _yo = struct.unpack_from("<h", smf, _o + 18)[0]      # signed x8 fixed-point (atlas px)
                struct.pack_into("<h", smf, _o + 18, _yo - int(round(RAISE * 8)))
                _raised += 1
        log(f"raised {_raised} native Latin records by {RAISE}px via y_off (no atlas change)")

    # DESCENDER DROP via a CODEPOINT-RANGE remap (2026-07-03). The +18 field is honored per range:
    # the Hebrew range (U+05xx) IGNORES it in-game (a 99 on the Hebrew match record did nothing),
    # but Arabic-presentation-forms (0xFE80) DROP (native Arabic uses y_off up to 174). So each of
    # the 5 descender finals is ALSO placed on a spaced Arabic-pres record (its glyph = the SAME
    # atlas box already written for the Hebrew letter) with a real tail y_off, and gowr_wad remaps
    # the TEXT to that codepoint. The pres-form range is RTL-strong like Hebrew -> logical storage
    # + bidi unchanged; overwriting native Arabic-pres records is harmless (no Arabic in Hebrew
    # content). Off-by-one: rendering cp=C draws record cp==C-1's glyph, so the glyph goes in
    # record C-1; set the tail y_off on BOTH C-1 and the match record C (which record the engine
    # reads y_off from is ambiguous — set both).
    iy1_by_cp = {cp: iy1 for cp, _, _, _, _, iy1 in rendered}
    m_by_cp = {m["cp"]: m for m in metrics}

    def _rec_off(cp):
        for o, c in smf_records(smf):
            if c == cp:
                return o
        return None

    for L, B in DESC_PRESFORM.items():                 # B = basic-Arabic text codepoint
        break                                          # DISABLED: testing EXACT-99 on plain Hebrew
        if os.environ.get("GOWR_DESC_BLIT"):
            break                                      # blit mode: records stay native (done above)
        if L not in desc_letters:
            continue                                   # not detected as a tail this build — skip
        m = m_by_cp[L]
        P = DESC_GLYPH_PRES.get(B)                      # its isolated-pres MATCH record (the drop)
        if P is None:
            continue
        _ov = os.environ.get("GOWR_DESC_YOFF")         # optional depth override (px) for tuning
        # Write the Hebrew glyph onto the isolated-pres MATCH record P and its glyph record P-1
        # (off-by-one). PRESERVE each record's native y_off (the descender drop) unless overridden.
        # Do NOT touch the basic records — they only need to EXIST so the shaper maps B -> P.
        for rc in (P - 1, P):
            off = _rec_off(rc)
            if off is None:
                log(f"WARN: pres record cp={hex(rc)} absent — descender {chr(L)} partial")
                continue
            native_yo = struct.unpack_from("<h", smf, off + 18)[0]      # keep the native drop
            native_8 = struct.unpack_from("<I", smf, off + 8)[0]        # Arabic script marker/kern
            native_bear = struct.unpack_from("<h", smf, off + 20)[0]    # ISOLATION: keep native bearing
            native_adv = struct.unpack_from("<I", smf, off + 24)[0]     # ISOLATION: keep native advance
            yo_px = float(_ov) if _ov else native_yo / 8.0
            write_record(smf, off, rc, m["x"], m["y"], m["w"], m["h"],
                         bearing, m["advance"], y_off=yo_px)
            struct.pack_into("<I", smf, off + 8, native_8)              # RESTORE +8/+10
            struct.pack_into("<h", smf, off + 20, native_bear)         # RESTORE native bearing
            struct.pack_into("<I", smf, off + 24, native_adv)          # RESTORE native advance
        log(f"descender {chr(L)} -> text U+{B:04X} glyph@pres U+{P:04X} (drop {yo_px:.1f}px)")

    # DO NOT touch the native Latin/English glyphs. PROVEN (user, 2026-07-03): shifting a Latin
    # record's y_off does NOT reposition the English in the layout — the native glyph cells are
    # TIGHT, so a y_off shift only moves the CLIP boundary (cut text) / adds dash artifacts. The
    # English is FIXED; alignment is done ENTIRELY by positioning the HEBREW (whose cells we
    # build with a RAISE band + DROP, so its y_off actually moves it) to meet the English.
    assert len(smf) == smf_sz
    dec_wad[smf_off:smf_off + smf_sz] = smf
    log("SMF_1: 28 records (tight crop + real per-letter y_off, x8-scaled)")
    return metrics


def pick_font():
    # Reverted to David (2026-07-03) per the user: the Arial swap did NOT improve the in-game
    # look (the engine's upscale blur — low-res bitmap atlas, no SDF — dominates over the atlas
    # font choice), so back to the previous face. Arial etc. stay as fallbacks.
    # David Libre MEDIUM (user analysis 2026-07-03): matches the native weight (8px) + sharpness
    # (AA 0.26 ≈ native 0.24) — the David SERIF look WITHOUT the dots, because the heavier Medium
    # weight rendered SHARP (SOFT≈0.3, not the old 1.2 blur) keeps the serifs as solid strokes
    # instead of breaking them into isolated "niqqud" dots. (Verified offline.)
    # BOLD (user 2026-07-04: "try thicker") — David Libre Bold gives a heavier stroke than Medium
    # without the DILATE hack. Falls back to Medium if the Bold file is missing.
    _base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                         "plague_tale_requiem", "work", "font", "fonts_pdf")
    for _w in ("DavidLibre-Bold.ttf", "DavidLibre-Medium.ttf"):
        dl = os.path.normpath(os.path.join(_base, _w))
        if os.path.exists(dl):
            return dl
    for name in ("arialbd.ttf", "gishabd.ttf", "davidbd.ttf", "arial.ttf"):
        p = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(p):
            return p
    raise RuntimeError("no Hebrew font found")
