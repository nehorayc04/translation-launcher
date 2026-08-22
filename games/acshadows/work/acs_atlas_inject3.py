#!/usr/bin/env python3
"""
acs_atlas_inject3.py -- Hebrew with CORRECT metrics, plus a size LADDER.

WHY v3
------
v2 wrote only pixels + codepoint because v1's metric rewrite "was the bug". It was not:
the real fault was a 4-byte-late record parse that paired every glyph with the NEXT
record's codepoint (see acs_atlas_inject._records). With that fixed, v2 put real Hebrew on
screen -- but every letter inherited its donor Arabic ligature's advance, and the donors
are picked largest-area-first, so spacing came out 2.5x-12x too wide and lines wrapped.

MEASURED from the game's OWN Arabic glyphs (never guessed):
    base-letter yMax (height above baseline) median  33.9 px   <- the "cap" to match
    base-letter advance median                       28.8 px
    base-letter xMin median                          -6.5 px   <- the raster's left pad
    donor slot advances                              72..353 px  <- the noise on screen
    donor capacity (W*H)                             5,733..23,121 B
    a 34 px Hebrew glyph needs ~40x46 = 1,840 B      -> fits every donor with room to spare

So: rewrite advance/bbox/W/H, rasterize at a measured body height, keep tex_offset.

THE LADDER (one build, one screenshot, zero extra launches)
-----------------------------------------------------------
The two proof labels use DISJOINT letters -- `moshe chadash` = {mem,shin,het,qof,dalet} and
`te'ina` = {tet,ayin,yod,nun,he} -- so each group can carry a different body height. The
screenshot then names the right one, and if both groups look identical the engine is
ignoring these metrics entirely (equally decisive).

    python acs_atlas_inject3.py --dry
    python acs_atlas_inject3.py --apply     # GAME MUST BE CLOSED
    python acs_atlas_inject3.py --revert
"""
import json
import os
import struct
import sys
import unicodedata

import numpy as np
from PIL import Image, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_cfd as C              # noqa: E402
import acs_atlas_inject as AI    # noqa: E402
import acs_stream_probe as SP    # noqa: E402
import acs_atlas_inject2 as I2   # noqa: E402

EDGE = AI.EDGE
PAD = 6                  # px of margin around the ink; matches the shipped |xMin| ~ 6.5
GROUP_A = set("משחקד")   # letters of the "New Game" label
GROUP_B = set("טעינה")   # letters of the "Load" label

# LADDER 1 (answered in-game 2026-08-21): body 34 vs 42.
#   -> the two rows rendered at visibly DIFFERENT sizes, so the engine DOES honor these
#      metrics, and 34 (== the measured Arabic cap of 33.9) matched while 42 was too big.
#      It also removed the line wrapping, confirming the advance rewrite reaches layout.
BODY = 34                # settled; both groups now share it so only ONE variable moves

# LADDER 2 (answered in-game): advance 1.12 x ink vs 0.88 x ink.
#   -> 0.88 made letters TOUCH; 1.12 was slightly loose. Then measuring the donor font
#      itself settled it: David Bold's own advance/ink ratio has median 1.121 -- so 1.12
#      was never the wrong NUMBER, it was wrong to use ONE number. The natural ratio runs
#      1.01 (bet, dalet) to 1.27 (gimel), so a flat multiplier over-spaces wide letters and
#      cramps narrow ones, which is exactly the unevenness on screen.
#   => use the font's OWN per-letter advance. No ladder can beat the designer's value.
#
# LADDER 3 (this build): the SDF curve. Measured, the shipped Arabic field tops out around
#   150 with a soft midtone band; mine reaches 176. Density itself is NOT comparable (an
#   Arabic glyph is a thin stroke in a big box, mine is tight-padded), so the amplitude is
#   the honest lever to test.
#   -> ANSWERED in-game: amplitude 44 rendered thin and washed out (barely more than an
#      outline), 96 read solid. Lesson: this field is a COVERAGE-derived band, not a true
#      distance field, so "match the game's max value of 150" was the wrong target -- the
#      same number means different things in the two encodings, and narrowing the band just
#      starves the engine's threshold. SETTLED at 96 for every letter.
SDF_AMP_A = SDF_AMP_B = 96.0

# LADDER 4 (this build): CARRIER CODEPOINTS vs Hebrew codepoints -- the root-cause test.
#   Hebrew glyphs render, but the WORDS still do not lay out right. AC Black Flag Resynced
#   (same atlas class 0xCBD4939A) hit exactly this and solved it by NOT using Hebrew
#   codepoints at all: it stored the text as rare Arabic ligature codepoints whose slots were
#   repainted with Hebrew art, so the engine sees a strong-RTL ARABIC run, applies its NATIVE
#   bidi (right-aligned, correct order) and paints Hebrew.
#   Verified safe: all 135,096 stored Arabic strings contain ZERO presentation-form codepoints
#   (the game stores BASE letters; the shaper makes the forms at runtime), so no legitimate
#   string can collide with a carrier.
#   -> ✅ ANSWERED IN-GAME 2026-08-21, and it is THE root cause. The carrier row rendered
#      `tet ayin yod nun he` right-to-left, correct order, even spacing, fully readable, while
#      the Hebrew-codepoint row beside it stayed scrambled. The engine gives a HEBREW run no
#      bidi at all in the Arabic locale -- it paints the letters in STORAGE order -- but a run
#      of Arabic codepoints gets the native RTL treatment. Glyphs, metrics and calibration were
#      never the problem; the CODEPOINT IDENTITY was.
#      => every letter is now a carrier.
CARRIER = set(AI.HEB)
CARRIER_MAP = {}                 # filled during injection, written to carrier_map.json
MIN_CAP = 2800                   # a 34 px Hebrew glyph needs at most ~48x54 = 2,592 bytes

# The carrier set proven end-to-end on AC Black Flag Resynced (same atlas class 0xCBD4939A).
# Reused wherever the same codepoint exists in the Shadows atlas -- prior art beats a fresh
# guess, and 17 of the 27 are available here.
_acbf = os.path.join(HERE, "..", "..", "acblackflag-resynced", "work", "carrier_map.json")
ACBF_CARRIERS = ({int(k, 16): int(v, 16)
                  for k, v in json.load(open(_acbf, encoding="utf-8")).items()}
                 if os.path.isfile(_acbf) else {})


def body_for(ch):
    return BODY


def sdf_amp(ch):
    return SDF_AMP_B if ch in GROUP_B else SDF_AMP_A


def render(ch, body, font_path=AI.HEB_FONT):
    """Rasterize `ch` with its ink exactly `body` px tall, on a shared baseline, padded.

    Returns (bytes, w, h, ink_w). Keeps the SDF curve v2 already proved on screen -- only
    the SIZE and the metrics change here, one variable at a time.
    """
    SS = 8
    lo, hi, best = 4, body * 4, None
    for _ in range(16):                      # binary-search the pt size for the ink height
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid * SS)
        m = f.getmask(ch, mode="L")
        if not m.size[0] or not m.size[1]:
            lo = mid + 1
            continue
        img = Image.new("L", m.size, 0)
        img.paste(Image.frombytes("L", m.size, bytes(m)), (0, 0))
        bb = img.getbbox()
        ih = (bb[3] - bb[1]) / SS
        best = (img, bb, f)
        if ih < body:
            lo = mid + 1
        else:
            hi = mid - 1
    img, bb, fnt = best
    gw = max(1, round((bb[2] - bb[0]) / SS))
    gh = max(1, round((bb[3] - bb[1]) / SS))
    small = (img.crop(bb).resize((gw, gh), Image.BOX)     # BOX, not LANCZOS (no ringing)
                .filter(ImageFilter.GaussianBlur(0.6)))
    a = np.asarray(small, dtype=np.float32) / 255.0
    amp = sdf_amp(ch)
    sdf = np.clip(EDGE + (a - 0.5) * amp, 0, EDGE + amp / 2).astype(np.uint8)
    w, h = gw + 2 * PAD, gh + 2 * PAD
    canvas = np.zeros((h, w), dtype=np.uint8)             # 0 = far outside AND compressible
    canvas[PAD:PAD + gh, PAD:PAD + gw] = sdf
    # the font designer's own advance -- the ink sits flush at the pen (lsb folded into PAD),
    # so `advance - ink_width` reproduces exactly the designed inter-letter gap.
    return bytearray(canvas.tobytes()), w, h, gw, fnt.getlength(ch) / SS


_SHARED_DONORS = None


def shared_donors(letters, oodle):
    """One donor codepoint per letter, IDENTICAL in all 8 weights.

    🔴 Picking donors by area RANK inside each weight (what v1-v3 did) gives a different
    codepoint per weight, because the weights are different resolutions and their slots sort
    differently. That is invisible while we OVERWRITE the codepoint with Hebrew -- every
    weight ends up with 0x05D0+i either way -- but it breaks the moment a letter must keep
    its donor's Arabic codepoint as a CARRIER: the text stores one fixed codepoint, so only
    the weights that happened to rank that slot in the same position render it. Measured:
    3/8 weights had all 5 carriers, 5/8 had one.

    So rank by the MINIMUM capacity across all weights and take the same list everywhere.
    """
    global _SHARED_DONORS
    if _SHARED_DONORS is not None:
        return _SHARED_DONORS
    caps = None
    for _path, idx in AI.WEIGHTS:
        _f, _o, _s, _b, _c, dec = SP.pristine(idx, oodle)
        _g, _cnt, _st, recs = AI._records(dec)
        cur = {r["cp"]: r["W"] * r["H"] for r in recs
               if 0xFB50 <= r["cp"] <= 0xFEFF and r["W"] * r["H"] > 0}
        caps = cur if caps is None else {cp: min(v, cur[cp])
                                         for cp, v in caps.items() if cp in cur}

    def eligible(cp):
        # 🔴 NOT every presentation form is a usable carrier. Picking the biggest slots put
        # Hebrew on THREE-letter and whole-WORD ligatures (U+FD69..FDFD; U+FDFD is the
        # bismillah, an entire phrase), and in-game those rows came out with extra glyphs and
        # scrambled -- one stored character can become several. The carriers proven on AC
        # Black Flag Resynced are all TWO-letter ligatures that expand to <= 2 characters.
        # So: cap the compatibility expansion, and never touch the FDF0..FDFD word block.
        return (caps.get(cp, 0) >= MIN_CAP
                and len(unicodedata.normalize("NFKC", chr(cp))) <= 2
                and not 0xFDF0 <= cp <= 0xFDFD)

    donors, used = [None] * len(letters), set()
    for i in range(len(letters)):            # 1) reuse ACBF's PROVEN carrier where it exists
        want = ACBF_CARRIERS.get(0x05D0 + i)
        if want and eligible(want) and want not in used:
            donors[i], _ = want, used.add(want)
    spare = [cp for cp, _v in sorted(caps.items(), key=lambda kv: -kv[1])
             if eligible(cp) and cp not in used]
    for i in range(len(letters)):            # 2) fill the rest from the clean pool
        if donors[i] is None:
            if not spare:
                raise RuntimeError("ran out of eligible carrier slots")
            donors[i] = spare.pop(0)
            used.add(donors[i])
    print(f"  carriers: {sum(1 for i in range(len(letters)) if donors[i] == ACBF_CARRIERS.get(0x05D0+i))}"
          f"/{len(letters)} reused from the AC Black Flag proven map")
    _SHARED_DONORS = donors
    return _SHARED_DONORS


def inject_metrics(dec, letters, zero_frac=1.0, donors=None):
    """Repurpose the largest presentation-form slots, writing the FULL record.

    `zero_frac` = how much of each donor slot's dead tail to overwrite with zeros. It is a
    CONTINUOUS knob on the object's compressibility, and it has to be tuned, because both
    extremes fail on the 12.8 MB weight (idx 20633, slot 3,312,307):

        zero_frac = 1.0  -> 77,237 bytes zeroed -> object encodes 15,308 UNDER the slot,
                            and the reachable-size set has a HOLE right at the slot: the
                            closest any filler length got was slot-40, across 6 pools,
                            ~98,000 trials and two compression levels.
        zero_frac = 0.0  -> object encodes 5,815 OVER the slot -> does not fit at all.

    So `run()` binary-searches this to land the gap in a small positive band, which is the
    regime the (proven) v2 deploy sat in. **When an exact-fit search cannot find the needle,
    shrink the haystack instead of enlarging the search.**
    """
    _g, _c, _s, recs = AI._records(dec)
    if donors is None:                       # legacy path: rank inside this weight only
        cand = sorted([r for r in recs if 0xFB50 <= r["cp"] <= 0xFEFF and r["W"] * r["H"] > 0],
                      key=lambda r: -(r["W"] * r["H"]))[:len(letters)]
    else:                                    # the SAME donor codepoint in every weight
        by_cp = {r["cp"]: r for r in recs}
        cand = [by_cp[cp] for cp in donors if cp in by_cp]
    if len(cand) < len(letters):
        raise RuntimeError("not enough presentation-form slots")
    d = bytearray(dec)
    used = 0
    for gi, ch in enumerate(letters):
        r = cand[gi]
        cap = r["W"] * r["H"]
        body = body_for(ch)
        px, w, h, ink_w, nat_adv = render(ch, body)
        if w * h > cap:
            raise RuntimeError(f"U+{0x05D0 + gi:04X}: {w}x{h} exceeds donor capacity {cap}")
        o, t = r["o"], r["toff"]
        # baseline at 0, y up: the ink spans 0..body and the box adds PAD on every side
        y_max = float(body + PAD)
        y_min = y_max - h
        x_min = float(-PAD)
        x_max = x_min + w
        adv = float(max(4, round(nat_adv)))                # the font's OWN advance
        # CARRIER letters keep the donor's ORIGINAL Arabic codepoint; the deploy then stores
        # the text as those codepoints, so the engine sees a strong-RTL ARABIC run and applies
        # its native bidi while painting our Hebrew. Everything else gets a Hebrew codepoint.
        if ch in CARRIER:
            CARRIER_MAP[ch] = r["cp"]
        else:
            struct.pack_into("<I", d, o + AI.CP_OFF, 0x05D0 + gi)
        struct.pack_into("<7f", d, o + AI.MET_OFF,
                         adv, x_min, y_min, x_max, y_max, float(w), float(h))
        d[t:t + w * h] = px
        # The bytes past w*h are never read (the engine takes exactly W*H, and W/H are ours),
        # so zeroing them is purely a compressibility lever -- see the docstring.
        dead = cap - w * h
        nz = int(dead * zero_frac)
        if nz:
            d[t + cap - nz:t + cap] = b"\x00" * nz
        used += 1
    return bytes(d), used


GAP_LO, GAP_HI = 1500, 7000     # the band v2 deployed in successfully (~5,700)


def tune_zero_frac(cfds, dec, letters, slot, oodle, tries=12, donors=None):
    """Binary-search how much dead tail to zero so the encoded object lands a SMALL amount
    under the slot. More zeros = more compressible = bigger gap; the relation is monotone."""
    di = max(range(len(cfds)), key=lambda i: len(cfds[i][0]))

    def gap_for(zf):
        nd, used = inject_metrics(dec, letters, zf, donors)
        enc = sum(len(C.build_cfd(nd if i == di else dd, ci, oodle, level=C.LEVEL))
                  for i, (dd, ci) in enumerate(cfds))
        return nd, used, slot - enc

    lo, hi = 0.0, 1.0
    nd, used, g = gap_for(hi)
    if g < GAP_LO:                       # even fully zeroed it does not fit -- nothing to tune
        return nd, used, hi, g
    best = (nd, used, hi, g)
    for _ in range(tries):
        mid = (lo + hi) / 2
        nd, used, g = gap_for(mid)
        if GAP_LO <= g <= GAP_HI:
            return nd, used, mid, g
        if g < GAP_LO:                   # too big -> need MORE zeros
            lo = mid
        else:                            # too much slack -> need FEWER zeros
            hi = mid
            best = (nd, used, mid, g)
    return best


def run(mode):
    oodle = C._oodle()
    letters = AI.HEB
    AI._POOL = os.urandom(4 << 20)
    donors = shared_donors(letters, oodle)      # identical in every weight -- see above
    print(f"  shared donors: " + " ".join(f"U+{c:04X}" for c in donors[:8]) + " ...")
    built = []
    for path, idx in AI.WEIGHTS:
        forge, off, size, blob, cfds, dec = SP.pristine(idx, oodle)
        nd, used, zf, gap = tune_zero_frac(cfds, dec, letters, size, oodle, donors=donors)
        assert len(nd) == len(dec)
        print(f"    idx={idx:<6} zero_frac={zf:.3f} -> gap {gap:+,}")
        nb = I2.exact_fill(cfds, nd, size, oodle)
        ok = nb is not None and len(nb) == size and AI._decoder_ok(nb)
        heb = 0
        if ok:
            c2, _ = C.decode_resource(nb, oodle)
            d2 = max((x for x, _ in c2), key=len)
            cps = {r["cp"] for r in AI._records(d2)[3]}
            want = [0x05D0 + i for i, c in enumerate(letters) if c not in CARRIER]
            heb = sum(1 for c in want if c in cps)
        print(f"  idx={idx:<6} ({os.path.basename(forge):<28}) slot={size:>10,} "
              f"written={used:<3} Heb={heb:>2}/{len(letters)-len(CARRIER)} "
              f"-> {'OK' if ok and heb == len(letters) - len(CARRIER) else 'FAIL'}")
        built.append((forge, off, size,
                      nb if (ok and heb == len(letters) - len(CARRIER)) else None))

    ready = [b for b in built if b[3] is not None]
    if mode != "--apply":
        print(f"\n--dry: {len(ready)}/{len(built)} weights built.")
        return 0 if len(ready) == len(built) else 1
    if len(ready) != len(built):
        print("\nnot all weights built -- aborting (never deploy a partial atlas set).")
        return 1
    for forge, off, size, nb in ready:
        AI.verify_slot(forge, off, size)     # the forge may have changed since the backup
        with open(forge, "r+b") as f:
            f.seek(off)
            f.write(nb)
        print(f"WROTE @0x{off:x} in {os.path.basename(forge)} ({size:,} B)")
    # 🔴 The atlas and the TEXT must agree about which letters are carrier-coded. If this map
    # is missing, acs_loc_deploy keeps storing Hebrew codepoints for letters whose slots no
    # longer answer to Hebrew -> those letters render as nothing. Write it with the deploy.
    with open(os.path.join(HERE, "carrier_map.json"), "w", encoding="utf-8") as fh:
        json.dump(CARRIER_MAP, fh, ensure_ascii=False, indent=1)
    print("\n  carrier_map.json: "
          + (", ".join(f"{k}->U+{v:04X}" for k, v in CARRIER_MAP.items()) or "(none)")
          + "\n  -> re-run acs_loc_deploy.py --proof so the TEXT uses these carriers")
    print(f"\nDEPLOYED -- calibration CONSOLIDATED; all three ladders answered in-game:\n"
          f"  body      {BODY}px                      (== the measured Arabic cap, 33.9)\n"
          f"  advance   the font's own, per letter   (a flat ratio WAS the unevenness)\n"
          f"  SDF amp   {SDF_AMP_A:.0f}                      (44 rendered washed out)\n"
          f"Every letter now uses identical settings -- no ladder. This is the shipping look.\n"
          f"Undo: python acs_atlas_inject3.py --revert")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1] if len(sys.argv) > 1 else "--dry"
    sys.exit(I2.revert() if a == "--revert" else run(a))
