#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_hebrew_font.py — THE correct Hebrew-glyph injector for A Plague Tale: Requiem.

Root cause of every prior "noise/dots" failure (found 2026-07-03): the DXT5 data
starts at texture-body BYTE 0 with a 4-byte TRAILER at the end — NOT a 4-byte
prefix header. The old code sliced body[:4]/body[4:], desyncing every DXT5 block
by 4 bytes -> the game read our writes as garbage. With the correct alignment the
atlas decodes to a CLEAN binary coverage map (alpha 0/255, 97% bimodal), and our
encoder is byte-faithful (validated vs Pillow's DXT5 = GPU truth).

Format (authoritative, widberg ImZouna Bitmap_Z + measured):
  * Texture object body = 512*512 DXT5 (BM_DXT5=16) at offset 0, then 4-byte trailer.
  * FontMap (Fonts_Z BIG_ARABIC) entry = cid,mat, adv(=topY), x0,y0,x1,y1 (atlas
    box px), bx,by, z.  topY model: box_bottom sits on baseline≈129 => adv = 129 - ascent
    (ascent = box-top -> glyph baseline).  Horizontal advance ≈ box_width + bx.
  * Glyph coverage lives in the DXT5 ALPHA (crisp binary); COLOR carries a soft gray
    copy (ink≈160). We write BOTH so the glyph is faithful whatever the shader samples.

Strategy: REPURPOSE 27 Arabic entries (constant FontMap size => guaranteed load,
proven), each pointing at a Hebrew glyph we DRAW into that Arabic glyph's own atlas
box (cleared first, so no neighbour is touched). Frank Ruehl Bold = dark serif for
the grim atmosphere.

Run:
  python build_hebrew_font.py            # build + OFFLINE Pillow verify (no deploy)
  python build_hebrew_font.py --deploy   # also copy to the live game (backs up once)
  python build_hebrew_font.py --revert   # restore the pristine backup
"""
from __future__ import annotations
import argparse, io, os, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from dpc_repack import DpcRepack
from fonts_z import FontsZ, char_to_cid, cid_to_char

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BIG = 0xAFBE3792DDA3B358
TEX_CLASS = 0xE9659CD1C3F3326D
HEBREW = [chr(c) for c in range(0x05D0, 0x05EB)]  # א..ת (27)
BACKUP = ".he_backup"
SIDE = 512
NPIX = SIDE * SIDE
BASELINE = 130            # line-top -> baseline (px). HIGHER = glyph sits LOWER on screen
#                           (adv=BASELINE-ascent). 130 per user "תוריד אותו למטה יותר".
# Hebrew body height in the atlas. HARD-CAPPED by the repurposed Arabic boxes: only
# 27 boxes are >= 55x74, so the tallest glyph (ל/ק) can be ~72px -> BODY_TARGET 54 is
# the MAX that still fits 27 slots (measured). Bigger needs a full atlas repack.
# SIZE MODEL (proven from the 40->28->18 test: text stayed big AND went blurry): the engine
# maps each glyph's DECLARED BOX to a FIXED requested size and scales the atlas glyph to fill
# it. A tight box => glyph fills the requested size => BIG; shrinking the atlas glyph just
# upscales a tiny bitmap => blurry. THE FIX: a UNIFORM, LARGE em-box (EM_BOX) with a hi-res
# glyph occupying only FILL=BODY_TARGET/EM_BOX of it -> the glyph renders at FILL x requested
# (SMALLER) and stays SHARP (a big atlas glyph downscaled, never upscaled). Lower BODY_TARGET
# (or raise EM_BOX) => smaller on-screen text.
BODY_TARGET = 36          # Hebrew ink height inside the em-box (px). Size knob: FILL=36/72=0.5
#                           -> Hebrew renders at ~half the (too-big) Arabic full size.
EM_BOX = 72               # UNIFORM declared box height (px) mapped by the engine to the fixed
#                           requested size; ~slot max (27 Arabic slots are >=55x74). All Hebrew
#                           share it => consistent size. Bigger EM_BOX or smaller BODY = smaller.
BASE_FRAC = 0.80          # baseline position within the em-box (0.80 => 20% below for descenders)
SIDE_PAD = 3              # horizontal padding inside the em-box (advance = glyph_w + 2*pad)
HERE_DIR = os.path.dirname(os.path.abspath(__file__))
# User pick (2026-07-12): Assistant REGULAR — clean modern sans, airy/open, LIGHTER than the
# previous Heebo Medium (which read too heavy/"dominant" = "too big"). Chosen from an offline
# WEIGHT_COMPARE at fixed height (on-screen SIZE is engine-locked; only weight/shape can change).
# History: David Libre = too bold/"silky"; Heebo Light = too thin/weak; Heebo Medium = too heavy.
# 🔴 2026-07-24: at the tiny 7 px body the user asked for, a 12.5 %-stroke Regular vanishes into
# pure AA (0.9 px stroke) — small text needs a RELATIVELY heavier weight to survive. Switched to
# Assistant-SemiBold, whose 24 %-at-17px lands at an appropriate ~1.7 px stroke at 7 px. (Regular
# stays the right pick at 17 px+; the weight tracks the size.)
DEF_FONT = r"C:\Windows\Fonts\opensanshebrew-regular-webfont.ttf"
# 🔴 WEIGHT was re-calibrated 2026-08-11 against the VANILLA ENGLISH in the SAME widget (the
# user's own screenshot with Text-language=English), which is a far better ruler than the native
# ARABIC: Arabic is a genuinely thin script, Hebrew is not, and matching the Arabic's 5.5% stroke
# is what made the Hebrew read washed-out beside the English. Measured stroke/body at body 30:
#   English (the target) 0.167 | Light 0.100 (SHIPPED, 40% too thin) | Regular 0.133 |
#   Regular+WEIGHT_SS=2 0.161 <== chosen | Bold 0.241 | Alef-regular 0.172 | Miriam 0.133
# Same family as the previously-approved letterforms — only the weight moves.
# (Superseded note, kept for context: the old pick was Light because the native Arabic is THIN
#  — 0.138 ink density, 5.5% stroke — and Light was the best cell-aspect 0.745 thin donor.)
# Stroke-to-body ratio at a fixed body height:
#   FrankRuhl-Reg 7.5 | Assistant-Light 10.0 | Heebo-Light 10.0 | Assistant-REGULAR 12.5 |
#   Heebo-Reg 15 | Assistant-SemiBold 18 | Heebo-Medium 17.5 | Assistant-Bold 25.
# The RIGHT target is not a guess and not the shipped Arabic — it is the ENGLISH the user is
# comparing against, measured off their screenshot: **11.8% of the body**. Assistant-Regular
# (12.5%) is the closest. Light (10%) was chosen while the body was 26-40 px, where it looked
# fine; at an 18 px body a 10% stroke is only 1.8 px and never forms a solid core — the glyph
# becomes pure anti-aliasing (measured AA mid/solid 1.38) and, magnified ~2.8x by the engine,
# reads as washed-out. Weight must be re-picked whenever the body size changes.
# The 7 Fonts_Z objects (from _diag_fonts): each context (title/menu/subtitle/body) uses a
# DIFFERENT one at a DIFFERENT native size. Only BIG_ARABIC has a full Arabic alphabet, so
# ALL Arabic-slot text currently FALLS BACK to it (big) -> Hebrew is always big. FIX: inject
# Hebrew into EVERY resolvable font at ITS OWN size, so each context renders Hebrew at the
# size it renders English (small subtitles stay small). oid -> human tag.
# SINGLE font: the game HARDCODES BIG_ARABIC for ALL Arabic-slot text (proven — injecting
# Hebrew into the small subtitle font did NOT shrink subtitles). So every context already
# routes here; injecting only here keeps size + weight + digits perfectly CONSISTENT
# (multi-font injection caused mixed sizes/quality across contexts).
FONT_OIDS = {
    0xAFBE3792DDA3B358: "BIG_ARABIC",   # the one font all Arabic-slot text uses
}
SS = 8                    # supersample. At a 26 px body a stroke is only ~2.6 px, so SS=4 left
#                           the edges lumpy and the stems visibly uneven = the "1930s letterpress"
#                           look. 8x costs nothing offline and cleans the downsample right up.
# The ORIGINAL alpha is CRISP (measured AA mid/solid=0.24) — depth comes from the colour
# GLOW, not from a blurred alpha. Over-blurring (0.6) made it fuzzy/rough. Keep it crisp.
EDGE_SOFT = 0.0           # ⚠️ 0, NOT a "tiny anti-jaggy blur". Chosen by rendering 4 curves at the
#                           SHIPPING body and upscaling them x2.8 the way the GPU does
#                           (_preview_curve.py): the BILINEAR magnification supplies all the
#                           smoothing there is, so any blur we add is applied twice and the result
#                           is mush. Sharper also means fewer mid-tones for DXT5 to quantise.
#                           AA mid/solid across the candidates: soft 0.87 · current 0.69 ·
#                           crisper 0.60 · CHOSEN 0.47 (the shipped font is 0.24 at a 62 px ink,
#                           and the ratio rises naturally as the glyph shrinks, so 0.47 at 21 px
#                           is the same edge character, not a harder one).
# THE colour channel = a FLAT gray plate, NOT a gradient (measured: the shipped Asobo font
# fills the colour/BC1 channel with a CONSTANT ~155 gray on every glyph, min 148 max 158).
# Our old code used a blurred GRADIENT glow (55->213); a gradient in the 5-bit BC1 channel
# BANDS into visible gray steps = the reported "רעש/פסים שחורים על האותיות ועל המספרים".
# A flat fill BC1-encodes with ZERO steps -> zero banding, and 155 matches the original's
# soft embossed depth (our old 213 was too bright/flat).
INK_GRAY = 157            # colour-channel value under FULL coverage (shipped font: 154..159)
# ---- THE REAL NOISE FIX (measured 2026-07-12 with _diag_glow.py — supersedes the flat-fill and
# the 'graded floor' attempts, BOTH of which were wrong) ----
# The shipped colour channel is a DISTANCE-RAMP GLOW around the glyph that decays to EXACTLY 0.
# Measured over the whole page, colour vs distance-from-ink (4-connected px):
#   d=0 157 | 1 120.7 | 2 106.1 | 3 91.6 | 4 77.2 | 5 63.0 | 6 49.0 | 7 35.0 | 8 21.2 | 9 10.4
#   | 10 4.9 | 11 1.7 | 12 0.3 | >=13 0.0 | far-from-any-ink 0.0
# The deltas are -14.6,-14.5,-14.4,-14.2,-14.0,-14.0,-13.8 => a PERFECT LINEAR ramp, 135 at d=0
# falling 14.3/px to 0 at d~=9.5 (clamped). NOT a gaussian (gaussian fit rms=15.5, wrong shape).
# What I shipped before: a FLAT 37 over the whole repurposed Arabic slot. Measured on the
# deployed atlas that gives far-background 14.4 (should be 0.0) -> a hard-edged dark RECTANGLE
# bigger than the letter, and inside the box the letter's counters sat at 37 (dark) where the
# original has 120->90 (bright). That is exactly the user's report: "a darker background inside
# the letters' cavity", "a perfect cut with no transition", "noise around the square that looks
# like bigger text behind it" (= the neighbours' glows just outside my rectangle).
GLOW_D0 = 135.0           # ramp value extrapolated to d=0
GLOW_MAX = 12             # dilation budget (>= the longest ramp we ever emit)
# ---- WHAT THE COLOUR CHANNEL ACTUALLY IS: the BLACK OUTLINE's coverage ----
# Confirmed in-game 2026-07-12: with the flat fill the user saw a dark RECTANGLE; the moment the
# ramp shipped they saw "a thick black FRAME hugging the letter". So the shader draws a black
# outline whose alpha is this channel — bright colour = opaque black halo, fading to 0.
# => the ramp's PIXEL length is the outline's THICKNESS, and it must scale with the glyph or a
# smaller letter gets a proportionally fatter frame. Shipped Arabic: ink 62 px with a 9.44 px
# ramp (135/14.3) = 15% of the body. Our 40 px Hebrew with the same 9.44 px ramp = 24% = the
# 1.6x-too-thick frame the user reported. Fix: ramp_len = RAMP_REF_LEN * ink_h / RAMP_REF_INK,
# carried PER GLYPH through the distance propagation (glyphs of different sizes coexist).
RAMP_REF_INK = 62.0       # mean ink height of the shipped Arabic glyphs
RAMP_REF_LEN = 9.44       # px at which the shipped ramp reaches 0 (= GLOW_D0 / 14.3)
# Hebrew body height (atlas px). = the English subtitle font's X-HEIGHT (SMALL_FONT 'o' = 41),
# NOT its cap (57): Hebrew has no lowercase, so cap-height Hebrew out-masses English text.
# Lower this to shrink the Hebrew further; raise it toward 57 to match English CAPS instead.
HEB_BODY = 40
# ---- SIZE LADDER round 2: vary the INK (see [[measure-with-a-ladder]]) ----
# Round 1 varied the declared BOX height (extending it DOWN into empty atlas space) and the user
# saw NO size difference. That is NOT the clean refutation it looks like: under the ordinary
# model (screen = ink * per-font scale) an empty box extension changes nothing either, so round 1
# was ALSO confounded. The only untested single variable left is the INK ITSELF, with the box
# kept tight. 3 groups interleaved across the alphabet so any sentence shows all three:
#   A (i%3==0) ink 40 px = the current build (control)
#   B (i%3==1) ink 26 px (-35%)
#   C (i%3==2) ink 16 px (-60%)  <- the reduction the user asked for
# A > B > C  => the ink drives the size; ship LADDER_INK[2] and the size problem is solved.
# A == B == C => the engine truly normalises every glyph to a fixed cell; the size is then
#                unreachable from the font and I say so instead of trying again.
# ✅ LADDER ANSWERED IN-GAME 2026-07-12: the three groups rendered at three clearly different
# sizes ("תוספות" — all group C — came out visibly smaller than "צא לשולחן העבודה"). So the
# ON-SCREEN SIZE FOLLOWS THE ATLAS INK, and the old "the engine normalises everything to a fixed
# cell" conclusion is WRONG — it came from the atlas-shrink test, which was confounded. The user
# picked group B, so ship a UNIFORM 26 px ink.
# ---- SIZE, MEASURED off the user's English|Hebrew side-by-side screenshot (_diag_screenshot.py),
# which is a calibrated ruler because BOTH scripts are drawn by the same engine in one image:
#   English (the game's own font): x-height 51 px · cap 69 px · stroke 11.8% · letter gap 17.6%
#   Hebrew  (26 px atlas ink)    : body     86 px            · stroke 10.5% · letter gap 18.6%
# => Hebrew was 1.25x the English CAP and 1.69x its x-height. Weight and spacing already match;
# only the size was off. Typographic norm for a Hebrew/Latin pair is body ~= 0.85 x cap (Hebrew
# has no lowercase, so every letter carries full height and reads bigger at an equal cap).
# I first applied the 0.85 refinement -> 18 px, and the user judged it WORSE in every way. Two
# reasons, both real: (a) 0.85*cap makes the Hebrew SMALLER than the English it is meant to match,
# and (b) 18 px throws away 17% of the atlas resolution in a font the engine already magnifies.
# The unambiguous reading of "the size of the English" is the CAP — Hebrew has no ascenders or
# descenders, so body == cap is the standard, conservative pairing:
#   target 69 px screen -> 26 * 69/86 = 21 px atlas ink  (vs the 26 px that read as too big).
# ⚠️ TARGET vs RENDERED are NOT the same number, and the offset MOVES with the alpha curve: with
# the old soft curve a target of 21 shipped a 22 px box; the crisp curve clips the fringe row so
# the same target ships exactly its own value. ALWAYS read the box heights back from the DEPLOYED
# file instead of trusting this constant.
# 🔴 SIZE, round 2 (2026-07-24): matching the English CAP (21 px → 69 screen) STILL read as "too
# big" to the user, and correctly so — English UI text is mostly lowercase, so a reader compares
# Hebrew to the x-HEIGHT (~51 screen), not the cap. Hebrew has no lowercase, so at equal cap it
# carries far more mass. Dropped to 17 px (≈56 screen), the perceptual midpoint between the cap and
# the x-height: a clear ~20% reduction that still keeps Assistant-Regular's stroke at the English's
# 12% (measured in _preview_weight17.py — the heavier fonts came out at 24%). The earlier 18 px
# attempt was rejected for THIN strokes + bad spacing + ragged heights, all fixed since.
# 🔴 SIZE, round 3 (2026-07-24): the user rejected 17 px too and asked EXPLICITLY for a ~70%
# reduction "from what there is now", in BOTH the UI and the subtitles (both render through
# BIG_ARABIC, so one change covers both). 70% of 17 ≈ 5 px, which the FLOOR preview
# (_preview_floor.py) shows at the ragged edge of legibility; 7 px (a ~60-73% reduction depending
# on the baseline) is still clearly readable, so ship 7 px with the heavier SemiBold (above) so
# the strokes survive at that size.
# 🔴🔴 SIZE, round 4 (2026-08-11) — "האותיות בסוף המשפט נחתכים" is a LINE-OVERFLOW, not a glyph
# defect. PROVEN: the deployed text really is 'לחץ על מקש כלשהו' (read back out of tt23.pc) but
# the start screen renders 'לחץ על מקש כלשה' — the final vav is gone ENTIRELY, and on the quit
# line the final he loses its detached left leg and reads as resh. The settings rows (a wide,
# right-aligned column) are pixel-perfect, so nothing is wrong with the glyphs: the engine CLIPS
# a line that is wider than its widget, and in RTL the clipped end is the LEFT = the end of the
# sentence. Hebrew is all cap-height, so it needs more width than the Latin the widget was sized
# for. The only lever that scales with line length is the BODY: 30 -> 28 makes every line 6.7 %
# narrower (start prompt 238 -> ~222 px, measured overflow was ~6.5 px). Do NOT fix this by
# cutting the tracking — measured against the vanilla English our gap is ALREADY ~19 % tighter.
LADDER_INK = (28, 22, 16)  # atlas ink height. TOGETHER WITH BOX_H_FIX this is the size:
#                           screen = REQ x ink / BOX_H_FIX.  (Alone it is only SHARPNESS — with a
#                           box derived from the glyph the ratio never moves, which is exactly the
#                           old "18/29/36 all render the same" result.)
LADDER = False            # uniform: one clean size.
# 🔑 THE SIZE KNOB — a FIXED declared box, padded symmetrically around the glyph.
#   screen_ink = REQ x ink / BOX_H_FIX.  MEASURED in the live settings menu (1600x900):
#   ink 40 / box 59 -> 22 px label, 41 px title  => REQ(menu) ~= 32.5, REQ(title) ~= 60,
#   REQ(start-screen prompt) ~= 48.  So ink 30 / box 70 -> ~14 px label = -37%.
# ⚠️ BOX_H_FIX is capped by the repurposable Arabic slots: at the widths we need there are
#   ~78 slots >= 59 px, ~54 >= 70, but only ~21 >= 80 and ~12 >= 90 (need 27). 70 is the ceiling;
#   go smaller than that ratio by lowering the INK, not by raising the box past 70.
BOX_H_FIX = 70            # 0 = derive a tight box from the glyphs
# 🔴🔴 HORIZONTAL PADDING — the "letters get cut at the end of the line" defect.
# MEASURED against the vanilla font: every shipped glyph leaves a 1 px transparent margin on
# BOTH sides of its ink inside the declared box (arabic gapL/gapR = 1/1, latin 1/1). Ours had
# 0/0 — the ink touched the box edge — and with bilinear filtering at a ~2.2x minification the
# outermost column is blended away. On a letter whose defining feature IS an edge stroke that
# is fatal: ה loses its left leg and reads as ר ("לשולחן העבודר").
# The advance is box_width + bx, so widening the box by 2 must be paid back in the bearing.
PAD_X = 1
# ---- 🔑 WEIGHT, calibrated against the VANILLA ENGLISH in the SAME widget ----
# The user's own screenshot with Text-language=English is the ruler: measured there the English
# label is x-height 12px with a 2.0px stroke => **stroke / body = 0.167** (±0.04 quantisation at
# that size). Our shipped Light rendered 0.100 — 40 % thinner — which on screen is a 1.4px stroke
# against English's 2.0px, and THAT is the "washed out / bad quality" difference, not the AA and
# not the resolution (mid/solid was already 0.31 vs the English's 0.36).
# Family weights measured at body 30 through the real render path: Light 0.100 · Regular 0.133 ·
# Bold 0.241 (too heavy) · Alef-regular 0.172 · Miriam 0.133.
# So: Regular + a sub-pixel outline to land mid-band.
WEIGHT_SS = 2             # extra stroke RADIUS in supersampled px (SS=8) => +2*2/8 = +0.5px width
FILL = 0.65               # 🔑 THE SIZE KNOB. render ≈ FILL x requested(~30px). SMALLER FILL = SMALLER
#                           on screen (proven model: 0.65 -> ~20px = the נ size). box is padded
#                           PROPORTIONALLY (both dims) so there is NO distortion.
REQ_PX = 30.0             # requested row height the engine asks for (measured in the menu, 1080p)
# ---- 🔑 SPAN CAPS — the second (and, with a uniform box, the ONLY) honest size knob. ----
# MEASURED, not assumed. Every one of the game's own 8 fonts declares a TIGHT box:
#   ink_h/box_h = 0.955..0.985 (mean 0.97), gap top 1-2 px, gap bottom 0-1 px, box_h and adv
#   BOTH per-glyph (BIG_ARABIC: 36 distinct box heights over its Arabic, 23 over its Latin).
# We must use ONE uniform box instead (a tight box makes each LINE self-normalise, so a line
# containing ל renders ~18% smaller than one without = the inconsistency), and the price of a
# uniform box is exactly the wasted head/foot room:
#        screen(ordinary letter) = REQ x body / (max_ascent + max_descent)
# So the two EXTREME glyphs alone decide how big all 21 ordinary letters render. Open Sans
# Hebrew Light is unusually long there — lamed 1.18 x body and tails 0.38 x body (ranked
# 89/422 of the machine's Hebrew fonts, ratio 0.645 -> only 19.4 px) — while ordinary Hebrew
# faces sit at Mehir 1.07/0.20, Miriam 1.15/0.20, Levenim 1.15/0.25. Capping to 1.12/0.30 is
# INSIDE that normal range, touches only ל and the five descenders, leaves the other 21 letters
# byte-identical, and buys the size back (ratio 0.645 -> ~0.70 => ~21 px = the user's "כמו נ").
LAM_CAP = 1.12            # lamed ascent      <= LAM_CAP  x body
DESC_CAP = 0.30           # deepest descender <= DESC_CAP x body
# ---- VERTICAL POSITION ----
# `adv` places the ink BOTTOM on the baseline, so a 26 px letter in a line box sized for the
# 79 px Arabic hugs the FLOOR of the row with a big gap above it ("צמוד ללמטה"). Centre the ink
# in the band [baseline-capH, baseline] instead: baseline_eff = baseline - (capH - ink)/2.
# Hebrew AND the repacked Latin share it so they stay on one line.
CENTER_IN_LINE = True
# ---- LETTER SPACING: `bx` is the only additive term we control, and the engine adds a FIXED
# component on top of it — so the gap does NOT shrink when the glyph does. Measured as a % of the
# body (scale-invariant, comparable across screenshots):
#   English (the target) 17.6%  |  26 px build (bx=2) 18.6% OK  |  18 px build (bx=2) 24.1% BAD
# At 18 px that is a 4.34 px gap where 3.17 px is wanted, so bx must drop by ~1.17.
# ⚠️ This is why simply shrinking the ink made everything WORSE: a word kept almost its old WIDTH
# at a smaller height, so labels still overflowed, still wrapped, and the wrapped line collided
# with the next row. The overlapping text was a SPACING bug, not a layout bug.
# Solving gap = bx + FIXED on the two measured builds gives FIXED ~= 2.6 px, so to hit the
# English's 17.6%:  bx = 0.176 * body - 2.6.   At body 21 -> 1.1.
# 🔑 bx is an f32 (SIGNED) in the FontsZ entry, so a NEGATIVE bearing IS allowed — the old
# `max(0, ...)` clamp was an unfounded safety assumption and it is EXACTLY what made the tiny
# build's tracking loose (user: "letters too far apart"): at 9 px the engine's FIXED ~2.6 px gap
# alone is 29% of the body, so bx MUST go negative to pull it back to English's 17.6%.
SIDE_BEARING = round(0.176 * LADDER_INK[0] - 2.6, 3)   # body 29 -> +2.5 (17.6% gap = English target).
#                           f32 signed: negative at a tiny body, positive here. Re-derives with size.
# ---- WIDTH / CONDENSE — the lever the vertical defects actually needed ----
# 🔴 THE NUMBERS IN THIS BLOCK ARE UNRELIABLE — do not build on them. They came from an
# autonomous capture taken while a STALE ELEVATED instance of the game was running (see
# [[stale-elevated-instance-fakes-no-change.md]]), so the window photographed was NOT this build,
# and the letter sample differs from the user's screenshot anyway (Hebrew letter widths vary a
# lot, so a median advance is only comparable on the same string). Re-measure with
# `_autocheck.py --attach`, which refuses to measure a process older than the deployed font.
# Measured in-game (my own capture, 1920x1080): per-letter ADVANCE is 84.4% of the body vs the
# English font's 75.5%, and a save-slot label needs 495 px where the column holds 378 px. That
# 24% overflow is what makes labels wrap, and a wrapped line lands on the NEXT slot's row = the
# "overlapping text". Hebrew is square by nature — the narrowest Hebrew font on this machine is
# still 76% wide/body vs the English 57% — so no font swap can fix it; the glyph has to be
# CONDENSED horizontally (height untouched).
#   advance = glyph_w + gap;  gap floor ~ 8% of body once bx = 0.
#   to fit 378/495 the advance must drop to ~64% of body -> glyph_w ~56% -> condense ~0.75-0.88.
CONDENSE = 1.00           # horizontal scale (1.0 = natural). 0.82 was measured to reach
#                           only 79% advance (64% needed) while thinning every vertical
#                           stem (AA mid/solid 0.82 -> 1.47) — condensing FIGHTS quality,
#                           so it must be paired with a heavier weight if ever used.
SC = (r"C:\Users\NEHORA~1\AppData\Local\Temp\claude"
      r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
      r"\68843b5c-b459-46d8-a07d-ec57b02321b0\scratchpad")


# ----------------------------- DXT5 codec ------------------------------ #
def _alpha_lut(a0, a1):
    if a0 > a1:
        return [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    return [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]


def decode_alpha(data, W=SIDE, H=SIDE):
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


def enc_alpha(cell):                      # 4x4 uint8 -> 8-byte DXT5 alpha (ADAPTIVE)
    # Use each block's OWN min/max as the endpoints (8-interpolated mode, a0>a1) so the
    # anti-aliased EDGE gets fine gradients instead of the coarse fixed-255/0 ramp -> far
    # smoother edges, killing the DXT5 edge-banding the subtitle/menu shader shows as noise.
    hi, lo = int(cell.max()), int(cell.min())
    if hi == lo:
        return bytes([hi, lo]) + b"\x00" * 6       # flat block -> all index 0 = hi
    lut = _alpha_lut(hi, lo)                        # hi>lo -> [hi, lo, +6 interp]
    bits = 0
    for i in range(16):
        v = int(cell[i // 4, i % 4])
        idx = min(range(8), key=lambda k: abs(lut[k] - v))
        bits |= idx << (3 * i)
    return bytes([hi, lo]) + bits.to_bytes(6, "little")


def _to565(v):
    r = (v >> 3) & 31; g = (v >> 2) & 63; b = (v >> 3) & 31
    return (r << 11) | (g << 5) | b


def decode_color(data, W=SIDE, H=SIDE):
    """decode the BC1 colour part (bytes o+8..o+16) to grayscale."""
    out = np.zeros((H, W), np.uint8); bpr = W // 4
    for by in range(H // 4):
        for bx in range(bpr):
            o = (by * bpr + bx) * 16 + 8
            c0 = struct.unpack_from("<H", data, o)[0]; c1 = struct.unpack_from("<H", data, o + 2)[0]
            bits = int.from_bytes(data[o + 4:o + 8], "little")
            g0 = ((c0 >> 11) & 31) * 255 // 31; g1 = ((c1 >> 11) & 31) * 255 // 31
            pal = [g0, g1, (2 * g0 + g1) // 3, (g0 + 2 * g1) // 3] if c0 > c1 else [g0, g1, (g0 + g1) // 2, 0]
            for i in range(16):
                out[by * 4 + i // 4, bx * 4 + i % 4] = pal[(bits >> (2 * i)) & 3]
    return out


def enc_color(cell):                      # 4x4 GRAY values (0..255) -> 8-byte BC1, adaptive
    hi, lo = int(cell.max()), int(cell.min())
    if hi == lo:
        return struct.pack("<HH", _to565(hi), _to565(hi)) + b"\x00\x00\x00\x00"
    c0, c1 = _to565(hi), _to565(lo)
    if c0 <= c1:                          # need c0>c1 for the 4-colour (non-alpha) mode
        c0, c1 = c1, c0; hi, lo = lo, hi
    pal = [hi, lo, (2 * hi + lo) // 3, (hi + 2 * lo) // 3]
    bits = 0
    for i in range(16):
        v = int(cell[i // 4, i % 4])
        idx = min(range(4), key=lambda k: abs(pal[k] - v))
        bits |= idx << (2 * i)
    return struct.pack("<HH", c0, c1) + bits.to_bytes(4, "little")


# --------------------------- Pillow = GPU truth ------------------------ #
def _dds(dxt5, w=SIDE, h=SIDE):
    hdr = bytearray(128); hdr[0:4] = b"DDS "
    struct.pack_into("<I", hdr, 4, 124)
    struct.pack_into("<I", hdr, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000)
    struct.pack_into("<I", hdr, 12, h); struct.pack_into("<I", hdr, 16, w)
    struct.pack_into("<I", hdr, 20, len(dxt5)); struct.pack_into("<I", hdr, 28, 1)
    struct.pack_into("<I", hdr, 76, 32); struct.pack_into("<I", hdr, 80, 0x4)
    hdr[84:88] = b"DXT5"; struct.pack_into("<I", hdr, 108, 0x1000)
    return bytes(hdr) + bytes(dxt5)


def gpu_rgba(dxt5):
    return np.array(Image.open(io.BytesIO(_dds(dxt5))).convert("RGBA"))


# ------------------------------ font render ---------------------------- #
def fit_size(path):
    for s in range(BODY_TARGET, BODY_TARGET * 3):
        f = ImageFont.truetype(path, s)
        b = f.getbbox("ה")
        if (b[3] - b[1]) >= BODY_TARGET:
            return s
    return BODY_TARGET * 2


def _render_canvas(path, size, ch):
    """Supersampled render of ch on a SHARED canvas -> (alpha HxW float, baseline row)."""
    W, H, BL = 160, 200, 130
    f = ImageFont.truetype(path, size * SS)
    im = Image.new("L", (W * SS, H * SS), 0)
    d = ImageDraw.Draw(im)
    if WEIGHT_SS:
        # sub-pixel WEIGHT: an outline of WEIGHT_SS SUPERSAMPLED px = WEIGHT_SS/SS real px of
        # extra radius, i.e. +2*WEIGHT_SS/SS px of stroke width. Calibrated against the vanilla
        # English in the same widget (stroke/x-height 0.167) — see the WEIGHT_SS note.
        d.text((10 * SS, BL * SS), ch, fill=255, font=f, anchor="ls",
               stroke_width=WEIGHT_SS, stroke_fill=255)
    else:
        d.text((10 * SS, BL * SS), ch, fill=255, font=f, anchor="ls")
    im = im.resize((W, H), Image.BOX)   # skill Rule 5: BOX area-average, NOT LANCZOS (ringing ->
    #                                     a 4x halo = the "dots/noise" failure). Contrast is the curve.
    if EDGE_SOFT > 0:
        im = im.filter(ImageFilter.GaussianBlur(EDGE_SOFT))
    a = np.array(im).astype(np.float32)
    # Curve tuned so the mid/solid AA ratio lands near the shipped font's 0.24-0.35. Too crisp
    # (0.15) reads as jagged; too soft (0.43, from (a-8)*1.12 at the smaller 40px body) reads as
    # fuzzy AND gives DXT5 more mid-tones to quantise = extra edge noise.
    # ⚠️ TWO OPPOSING PRESSURES, and the screenshot settles which wins.
    # The "1930s letterpress" roughness came from SS=4 (bad sampling), NOT from crispness — fixed
    # by SS=8. Meanwhile the SCREENSHOT shows the engine UPSCALES our atlas glyph ~2.8x (Hebrew
    # stroke 7.4 px on screen from 2.6 px in the atlas) while its own English font upscales only
    # ~1.2x. Under a 2.8x magnification a soft atlas edge becomes a WIDE mushy edge, so the gentle
    # curve I tried at 26 px was the wrong direction: with SS=8 we can be well-sampled AND crisp.
    # 🔴 THE CURVE IS SIZE-ADAPTIVE. The crisp (a-22)*1.90 was chosen for a LARGE glyph blown up
    # ~2.8x, where a soft edge becomes mush. At a TINY body (7-11 px) the whole glyph is only a few
    # pixels and most of them are faint AA — the crisp curve + a[a<10]=0 then ZEROES the letter down
    # to a 1 px ghost (measured: 4/27 solid at 7 px). Small text needs the OPPOSITE: preserve
    # coverage so a stroke exists at all. Gate on the shipped body size.
    if LADDER_INK[0] <= 20:   # small bodies (<=20px): moderate AA curve keeps grey edges (Word-like)
        # 🔴 TINY bodies (7-11 px): the enemy is not edge-softness but DXT5 quantisation — a 4x4
        # block with only 8 interpolated alpha levels drops a faint tiny glyph to nothing. A gentle
        # curve made it WORSE (0/27 solid, all mid-tone); a HIGH-CONTRAST curve pushes coverage to
        # solid so it survives the encode. Measured through the real enc_alpha pipeline at 7 px:
        # gentle 342 solid px · crisp 437 · (a-24)*4.0 590. High contrast wins decisively here.
        # ×3.6 hard-clipped into chunky letterpress blobs (user: "not like Word"). A MODERATE
        # curve keeps grey AA edges (Word renders anti-aliased, not hard-clipped), which the
        # engine's bilinear upscale then smooths — while still enough contrast to survive DXT5.
        # (offline A/B through the real codec at 1.65x & 3.4x, _preview_fix.py: this reads cleanest.)
        a = np.clip((a - 14.0) * 2.0, 0, 255)
        a[a < 8] = 0
    else:
        a = np.clip((a - 22.0) * 1.90, 0, 255)   # crisp, for large bodies (see _preview_curve.py)
        a[a < 10] = 0
    return a.astype(np.uint8), BL


def _render_set_ss(path, size, chars):
    """Render the alphabet and normalise every glyph's vertical extent IN THE SUPERSAMPLED
    DOMAIN, then downsample — returns {ch: (alpha, BL)} exactly like `_render_canvas` did.

    🔴🔴 WHY IN SS AND NOT ON THE FINISHED BITMAP. Normalising the 31 px bitmap means SOME
    letters get a LANCZOS stretch (30 -> 31) while the others are untouched, so the resampled
    ones come out a shade softer/heavier — a NEW inconsistency traded for the old one. At SS=8
    the same correction is a 240 -> 248 row resample, 8x finer than a pixel, and EVERY glyph
    goes through the identical path, so no letter is treated differently.

    Guarantees, all measured afterwards in the deployed atlas: every ordinary letter's ink
    occupies the SAME rows; the descenders share one body and one tail depth; lamed keeps a
    capped ascender; yod keeps its own height AND its float above the baseline.
    """
    W, H, BL = 160, 200, 130
    BLS = BL * SS
    f = ImageFont.truetype(path, size * SS)
    raw = {}
    for ch in chars:
        im = Image.new("L", (W * SS, H * SS), 0)
        d = ImageDraw.Draw(im)
        if WEIGHT_SS:
            d.text((10 * SS, BLS), ch, fill=255, font=f, anchor="ls",
                   stroke_width=WEIGHT_SS, stroke_fill=255)
        else:
            d.text((10 * SS, BLS), ch, fill=255, font=f, anchor="ls")
        raw[ch] = np.array(im)
    # ink extents (SS rows), split at the baseline
    ext = {}
    for ch, a in raw.items():
        ys = np.where((a > 127).any(axis=1))[0]
        ext[ch] = (int(ys.min()), int(ys.max())) if len(ys) else None
    std = [ext[c] for c in chars
           if c not in _HE_TALL + _HE_DESC + _HE_SHORT and ext[c]]
    if not std:
        return {ch: _render_canvas(path, size, ch) for ch in chars}
    top_t = int(np.median([t for t, _b in std]))
    body_ss = BLS - top_t                       # ordinary ink height, in SS rows
    max_over = max(0, int(round((LAM_CAP - 1.0) * body_ss)))
    max_desc = max(SS, int(round(DESC_CAP * body_ss)))
    out = {}
    for ch in chars:
        a = raw[ch]
        if ext[ch] is None:
            out[ch] = _finish_ss(a, W, H), BL
            continue
        up = a[:BLS]
        yu = np.where((up > 127).any(axis=1))[0]
        dn = a[BLS:]
        yd = np.where((dn > 127).any(axis=1))[0]
        new = np.zeros_like(a)
        if len(yu):
            band = up[yu.min():yu.max() + 1]
            gap = BLS - (int(yu.max()) + 1)     # ink bottom -> baseline (yod floats)
            if ch in _HE_SHORT:
                tgt = band.shape[0]
            elif ch in _HE_TALL:
                tgt = body_ss + min(max(band.shape[0] - body_ss, 0), max_over)
            else:
                tgt = max(SS, body_ss - gap)
            band = np.array(Image.fromarray(band, "L").resize(
                (band.shape[1], tgt), Image.LANCZOS)) if band.shape[0] != tgt else band
            y0 = BLS - gap - tgt
            new[y0:y0 + tgt] = band
        if len(yd):
            gap = int(yd.min())
            band = dn[yd.min():yd.max() + 1]
            tgt = min(band.shape[0], max(SS, max_desc - gap))
            band = np.array(Image.fromarray(band, "L").resize(
                (band.shape[1], tgt), Image.LANCZOS)) if band.shape[0] != tgt else band
            y0 = BLS + gap
            new[y0:y0 + tgt] = np.maximum(new[y0:y0 + tgt], band)
        out[ch] = (_finish_ss(new, W, H), BL)
    return out


def _finish_ss(arr, W, H):
    """SS array -> the finished alpha (BOX downsample + the size-adaptive contrast curve)."""
    im = Image.fromarray(arr, "L").resize((W, H), Image.BOX)
    if EDGE_SOFT > 0:
        im = im.filter(ImageFilter.GaussianBlur(EDGE_SOFT))
    a = np.array(im).astype(np.float32)
    if LADDER_INK[0] <= 20:
        a = np.clip((a - 14.0) * 2.0, 0, 255)
        a[a < 8] = 0
    else:
        a = np.clip((a - 22.0) * 1.90, 0, 255)
        a[a < 10] = 0
    return a.astype(np.uint8)


def _crop(a, BL, top=None, bot=None):
    """Crop to the ink box, optionally forcing a shared top and/or bottom. -> (glyph, ascent)."""
    ys, xs = np.where(a > 10)
    if len(ys) == 0:
        return np.zeros((8, 8), np.uint8), 8
    t, b, l, r = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    if top is not None:
        # The shared cap line wins UNCONDITIONALLY, in both directions: a letter starting low is
        # padded with transparent rows, a letter starting high loses its fringe.
        # ⚠️ Two earlier attempts failed here and both are worth remembering:
        #   1. `min(t, top)` only pads upward, so the letters that were already too TALL kept
        #      their extra row and nothing was unified at all.
        #   2. Guarding the trim on "the rows are faint (<128)" made the unification depend on
        #      the ALPHA CURVE — sharpening the curve raised the fringe values, the guard started
        #      refusing, and the cap line broke apart again (13 letters at 20 px, 7 at 21 px).
        # Rows above the shared cap are sub-128 by construction (see render_set), so dropping
        # them is safe without a second, curve-sensitive test.
        t = max(0, min(int(top), b))
    if bot is not None:
        # 🔴 Unifying only the TOP is not enough: the height is bottom-minus-top, and the letters
        # all sit on the SAME baseline yet their bottom AA row varies with the shape of the foot
        # (a curved foot bleeds one row further than a flat one). Fixing the cap alone still left
        # 13 letters at 20 px and 7 at 21 px — the variance had simply moved to the other end.
        b = min(a.shape[0] - 1, max(int(bot), t))
    g = a[t:b + 1, l:r + 1]
    if CONDENSE != 1.0:                      # narrow the glyph, keep its height
        h, w = g.shape
        nw = max(2, int(round(w * CONDENSE)))
        g = np.array(Image.fromarray(g).resize((nw, h), Image.LANCZOS))
    return g, int(BL - t)


def render_letter(path, size, ch):
    """Render ch SUPERSAMPLED then downscale -> soft anti-aliased coverage (not razor
    sharp). Return (glyph HxW uint8 coverage, ascent) where ascent = ink-top -> baseline."""
    a, BL = _render_canvas(path, size, ch)
    return _crop(a, BL)


# Letters whose ink LEGITIMATELY leaves the standard band and must keep their own extent:
_HE_TALL = "ל"                                  # lamed — ascender
_HE_DESC = "ךןףץק"          # final kaf/nun/pe/tsadi + qof — descenders
_HE_SHORT = "י"                                 # yod — small and high


def render_set(path, size, chars):
    """Render a whole alphabet against ONE shared cap line.

    🔴 THE DEFECT THIS FIXES: cropping every glyph to its OWN ink bbox lets sub-pixel rounding put
    the ink top one row higher or lower per letter. In the atlas that is 1 px — but the engine
    magnifies BIG_ARABIC ~3.3x, so it reads on screen as "some letters are shorter". Measured on
    the deployed build: 11 letters at 21 px and 9 at 22 px, split ARBITRARILY (vav 22 vs zayin 21,
    mem 22 vs final-mem 21 — pairs that share a cap line in the source font), so it is quantisation
    noise, not the optical overshoot a designer draws.

    Fix: anchor every STANDARD letter at the MEDIAN ink-top, so all their boxes share one height;
    a letter whose ink starts a row lower simply gains one transparent row (invisible, and the
    outline ramp is regenerated from the final alpha anyway). Letters that genuinely differ —
    yod, lamed and the descenders — keep their own extent.
    See [[screenshot-is-a-calibrated-ruler]] and the AC2 "forced ascent" note.
    """
    canvas = _render_set_ss(path, size, chars)
    tops, bots = [], []
    for ch, (a, _) in canvas.items():
        if ch in _HE_TALL + _HE_DESC + _HE_SHORT:
            continue
        # 🔑 Define the cap and baseline rows by SUBSTANTIAL ink (>=128), not by the first
        # non-zero pixel. The faint fringe row moves with the alpha curve, so a fringe-based
        # anchor makes the whole unification curve-dependent — which is exactly how it silently
        # broke once when the curve was sharpened.
        ys, _xs = np.where(a >= 128)
        if len(ys):
            tops.append(int(ys.min()))
            bots.append(int(ys.max()))
    std_top = int(np.median(tops)) if tops else None
    std_bot = int(np.median(bots)) if bots else None
    out = {}
    for ch, (a, BL) in canvas.items():
        # lamed alone rises above the cap; yod alone stops short of the baseline; the five
        # descenders alone drop below it. Everything else shares BOTH anchors.
        top = None if ch in _HE_TALL else std_top
        bot = None if ch in _HE_DESC + _HE_SHORT else std_bot
        out[ch] = _crop(a, BL, top, bot)
    return out


def _vscale(band, n):
    """Resample a band to n rows, width unchanged (LANCZOS keeps the stroke smooth)."""
    h, w = band.shape
    if h == n or h == 0 or n <= 0 or w == 0:
        return band
    return np.array(Image.fromarray(band, "L").resize((w, n), Image.LANCZOS))


def _ink_band(band):
    """The rows of `band` that actually carry ink (>=40), or None."""
    if band.shape[0] == 0:
        return None
    ys = np.where((band >= 40).any(axis=1))[0]
    return None if not len(ys) else band[ys.min():ys.max() + 1]


def cap_span(gset):
    """DEPRECATED passthrough. The vertical normalisation + the LAM_CAP/DESC_CAP capping now
    happen inside `_render_set_ss` at SUPERSAMPLED resolution, where the correction is 8x finer
    than a pixel and every glyph gets the identical treatment. Doing it here, on the finished
    31 px bitmap, resampled only SOME letters and made them a shade softer than the rest — a new
    inconsistency in place of the old one. Kept so the diagnostic scripts keep importing."""
    return gset


LATIN_CAP = 36            # Latin cap-height inside the em-box — matches BODY_TARGET so Latin
#                           names/digits render at the SAME small size as the Hebrew.


def fit_cap(path, target):
    """font size whose cap 'H' is ~target px tall."""
    for s in range(target, target * 3):
        b = ImageFont.truetype(path, s).getbbox("H")
        if (b[3] - b[1]) >= target:
            return s
    return target * 2


def fit_body(path, target):
    """font size whose Hebrew body ('מ') is ~target px tall."""
    for s in range(max(6, target), target * 3):
        b = ImageFont.truetype(path, s).getbbox("מ")
        if (b[3] - b[1]) >= target:
            return s
    return target * 2


def font_metrics(fz, m2t, page_alpha):
    """Infer (cap_height, baseline) IN ATLAS PX for this specific font, from a reference
    Latin cap glyph. adv is line-top->ink-top; a cap sits on the baseline, so
    baseline = adv + cap_ink_height. Each font has its OWN scale, so Hebrew must be sized +
    positioned per-font (that is exactly what makes each context match the English size)."""
    for ref in "HELMNBDRT":
        for e in fz.entries:
            if cid_to_char(e.cid) == ref and e.mat in m2t:
                x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
                if x1 <= x0 or y1 <= y0:
                    continue
                a = page_alpha(m2t[e.mat])[y0:y1, x0:x1]
                ys, _ = np.where(a > 100)
                if len(ys) >= 2:
                    ih = int(ys.max() - ys.min() + 1)
                    return ih, int(round(e.adv)) + ih
    return 40, 130


def find_slots(fz, m2t, need_w, need_h, n=27):
    """n repurposable entries with a box >= need_w x need_h. Prefer Arabic-block glyphs
    (unused in Hebrew text); if a small font has too few, add HIGH-codepoint glyphs
    (CJK/symbols, cp>=0x2000) — never Latin/punct/digits/Hebrew."""
    def usable(e):
        return e.mat in m2t and (e.x1 - e.x0) >= need_w and (e.y1 - e.y0) >= need_h
    ar = [e for e in fz.entries
          if (lambda c: c and is_ar(ord(c[0])))(cid_to_char(e.cid)) and usable(e)]
    ar.sort(key=lambda e: -(e.x1 - e.x0) * (e.y1 - e.y0))
    slots = ar[:n]
    if len(slots) < n:
        seen = {id(e) for e in slots}
        hi = [e for e in fz.entries
              if id(e) not in seen and usable(e)
              and (lambda c: c and len(c) == 1 and ord(c) >= 0x2000
                   and not (0x05D0 <= ord(c) <= 0x05EA))(cid_to_char(e.cid))]
        hi.sort(key=lambda e: -(e.x1 - e.x0) * (e.y1 - e.y0))
        slots += hi[:n - len(slots)]
    return slots


# --------------------------------- main -------------------------------- #
def resolve_mat_textures(byid, fz):
    mats = list(struct.unpack_from("<10Q", fz.tail, 4))
    texids = {o.oid for o in byid.values() if o.otype == TEX_CLASS}
    m2t = {}
    for i, mid in enumerate(mats):
        if mid not in byid:                      # some material ids aren't standalone objects
            continue
        b = byid[mid].info + byid[mid].body
        for off in range(0, len(b) - 8):
            if struct.unpack_from("<Q", b, off)[0] in texids:
                m2t[i] = struct.unpack_from("<Q", b, off)[0]; break
    return m2t


def is_ar(cp): return 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF


def _dist_from_ink(mask, maxd):
    """4-connected distance from the ink (0 inside it) — the SAME metric the shipped profile
    was measured with, so the ramp constants transfer exactly."""
    d = np.full(mask.shape, maxd + 1, np.int16)
    d[mask] = 0
    cur = mask.copy()
    for k in range(1, maxd + 1):
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]
        nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]
        nxt[:, :-1] |= cur[:, 1:]
        new = nxt & ~cur
        d[new] = k
        cur = nxt
    return d


def ramp_len(ink_h):
    """Outline thickness for a glyph whose ink is `ink_h` px tall — proportional to the shipped
    Arabic (62 px ink -> 9.44 px ramp), so a small letter never gets a fat black frame."""
    return max(2.0, RAMP_REF_LEN * float(ink_h) / RAMP_REF_INK)


def _dilate(mask, n):
    d = mask.copy()
    for _ in range(n):
        nxt = d.copy()
        nxt[1:, :] |= d[:-1, :]; nxt[:-1, :] |= d[1:, :]
        nxt[:, 1:] |= d[:, :-1]; nxt[:, :-1] |= d[:, 1:]
        d = nxt
    return d


def rebuild_colour(a, g, rmap, dirty_blocks):
    """Rebuild the COLOUR channel (= the black outline's coverage) from the FINAL alpha over
    every dirty region, with a PER-GLYPH ramp length.

    Regenerating instead of painting per glyph is both exactly correct (the shipped channel is a
    pure function of distance-from-ink) AND the only way to erase the halo of a REMOVED glyph: a
    repurposed Arabic slot's outline spilled up to ~9 px OUTSIDE the slot, so clearing the slot
    alone left that ring behind = colour with no ink under it = the ghost the user saw as "text
    behind the box, bigger than it".

    `rmap` holds each written glyph's ramp length stamped over its ink (0 = untouched ink, which
    keeps the shipped RAMP_REF_LEN). The length is PROPAGATED outward together with the distance
    so glyphs of different sizes can sit side by side and each keeps a proportional outline.
    Returns the block set to re-encode.
    """
    dirty = np.zeros(a.shape, bool)
    for (byk, bxk) in dirty_blocks:
        dirty[byk * 4:byk * 4 + 4, bxk * 4:bxk * 4 + 4] = True
    dirty = _dilate(dirty, GLOW_MAX + 4)          # cover the removed glyph's whole halo
    ink = a > 128
    d = np.full(a.shape, GLOW_MAX + 1, np.int16)
    d[ink] = 0
    rl = np.zeros(a.shape, np.float32)
    rl[ink] = np.where(rmap[ink] > 0, rmap[ink], RAMP_REF_LEN)
    cur = ink.copy()
    for k in range(1, GLOW_MAX + 1):
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]; nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]; nxt[:, :-1] |= cur[:, 1:]
        new = nxt & ~cur
        if not new.any():
            break
        spread = rl.copy()                        # carry the nearest glyph's ramp length out
        spread[1:, :] = np.maximum(spread[1:, :], rl[:-1, :])
        spread[:-1, :] = np.maximum(spread[:-1, :], rl[1:, :])
        spread[:, 1:] = np.maximum(spread[:, 1:], rl[:, :-1])
        spread[:, :-1] = np.maximum(spread[:, :-1], rl[:, 1:])
        d[new] = k
        rl[new] = spread[new]
        cur = nxt
    frac = d.astype(np.float32) / np.maximum(rl, 1e-6)
    col = np.clip(GLOW_D0 * (1.0 - frac), 0.0, 255.0)
    col[rl <= 0] = 0.0
    col = np.maximum(col, a.astype(np.float32) / 255.0 * INK_GRAY)
    g[dirty] = col[dirty]
    h, w = a.shape
    bmask = dirty.reshape(h // 4, 4, w // 4, 4).any(axis=(1, 3))
    return set(map(tuple, np.argwhere(bmask).tolist()))


def repack_latin(fz, font, load_page, m2t, touched, baseline, cap, box_h=0, base_in_box=0):
    """RESTYLE + RE-PACK all Latin/punct glyphs to the thin font at ONE fixed cap-height.
    The old boxes are scattered over many pages, so a per-page pack strands wide glyphs;
    fix: pool ALL freed boxes GLOBALLY and assign each glyph (most-constrained first) to a
    fitting box on ANY page (Kuhn matching), re-pointing e.mat. TIGHT box + adv=baseline-asc
    (correct advance; the em-box experiment broke inter-letter spacing / overlapped titles)."""
    size = fit_cap(font, cap)
    GAP = 3
    lat = [e for e in fz.entries
           if (lambda c: c and len(c) == 1 and 0x21 <= ord(c) <= 0x7E and c != "|")(cid_to_char(e.cid))]
    # clear every old Latin box; pool them (with their material + page) globally
    boxes = []                                 # [mat, tex, x, y, w, h]
    for e in lat:
        tex = m2t[e.mat]
        a, g, _tr, _rm = load_page(tex)
        x0, y0, x1, y1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
        a[y0:y1, x0:x1] = 0
        g[y0:y1, x0:x1] = 0
        blks = touched.setdefault(tex, set())
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                blks.add((yy // 4, xx // 4))
        boxes.append([e.mat, tex, x0, y0, x1 - x0, y1 - y0])
    glyphs = [[e, *render_letter(font, size, cid_to_char(e.cid))] for e in lat]
    # bipartite MAX MATCHING (Kuhn): edge glyph<->box iff the box fits the glyph. With 93
    # glyphs and 93 (bigger, overall) boxes a perfect matching exists -> every glyph keeps
    # its natural size (no shrink). Prefer the SMALLEST fitting box so big boxes stay free
    # for the glyphs that truly need them.
    edges = []
    for gi in range(len(glyphs)):
        gh, gw = glyphs[gi][1].shape
        fit = [b for b in range(len(boxes)) if boxes[b][4] >= gw + GAP and boxes[b][5] >= gh + GAP]
        # PREFER a box tall enough for the shared uniform height (so digits/punct end up on the
        # same box height as the Hebrew and a digits-only line renders at the same size), then
        # smallest. A preference only — the edge SET is unchanged, so the matching can't shrink.
        fit.sort(key=lambda b: (0 if box_h and boxes[b][5] >= box_h else 1,
                                boxes[b][4] * boxes[b][5]))
        edges.append(fit)
    match_box = [-1] * len(boxes)              # box -> glyph

    def kuhn(gi, seen):
        for b in edges[gi]:
            if not seen[b]:
                seen[b] = True
                if match_box[b] == -1 or kuhn(match_box[b], seen):
                    match_box[b] = gi
                    return True
        return False

    # match COMMON glyphs (letters/digits/basic punct) FIRST so they are guaranteed a box
    # at full size; only RARE symbols (+=~^{}[]\|@#$%&*_<>) may be left to shrink.
    common = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?()-:;'\"/")
    prio = sorted(range(len(glyphs)),
                  key=lambda i: (0 if cid_to_char(glyphs[i][0].cid) in common else 1, len(edges[i])))
    for gi in prio:
        kuhn(gi, [False] * len(boxes))
    glyph_box = [-1] * len(glyphs)
    for b, gi in enumerate(match_box):
        if gi != -1:
            glyph_box[gi] = b
    order, avail = [], [b for b in range(len(boxes)) if match_box[b] == -1]
    for gi in range(len(glyphs)):
        if glyph_box[gi] != -1:
            order.append((gi, glyph_box[gi]))
        else:
            order.append((gi, None))
            print(f"    WARN unmatched-shrink '{cid_to_char(glyphs[gi][0].cid)}'")
    for gi, b in order:
        e, gl, asc = glyphs[gi]
        gh, gw = gl.shape
        if b is None:
            b = max(avail, key=lambda i: boxes[i][4] * boxes[i][5]); avail.remove(b)
            rw, rh = boxes[b][4], boxes[b][5]
            sf = min((rw - GAP) / gw, (rh - GAP) / gh, 1.0)
            gl = np.array(Image.fromarray(gl).resize((max(1, int(gw * sf)), max(1, int(gh * sf))), Image.LANCZOS))
            asc = int(asc * sf); gh, gw = gl.shape
        mat, tex, rx, ry, rw, rh = boxes[b]
        a, g, _tr, rmap = load_page(tex)
        a[ry:ry + rh, rx:rx + rw] = 0          # clear the freed box, draw the glyph TIGHT
        g[ry:ry + rh, rx:rx + rw] = 0.0        # colour: rebuilt globally from the final alpha
        rmap[ry:ry + rh, rx:rx + rw] = 0.0
        # 🔑 SAME UNIFORM BOX as the Hebrew whenever the freed box can hold it: the engine
        # normalises a line by its TALLEST declared box, so a digits-only line ("0/12",
        # "24/07/26") whose boxes are tight would render MUCH bigger than the Hebrew lines
        # around it — exactly what the screenshots showed. One shared box height + one shared
        # baseline row keeps every line, mixed or not, at the same size and on one baseline.
        uni = box_h and base_in_box and rh >= box_h and base_in_box >= asc \
            and (box_h - base_in_box) >= (gh - asc)
        gy = ry + (base_in_box - asc) if uni else ry
        a[gy:gy + gh, rx + PAD_X:rx + PAD_X + gw] = gl
        rmap[gy:gy + gh, rx + PAD_X:rx + PAD_X + gw] = ramp_len(cap)   # outline ~ Latin cap
        blks = touched.setdefault(tex, set())
        for yy in range(ry, ry + rh):
            for xx in range(rx, rx + rw):
                blks.add((yy // 4, xx // 4))
        e.mat = mat                            # re-point to the (possibly different) page
        if uni:
            e.x0, e.y0, e.x1, e.y1 = float(rx), float(ry), float(rx + gw + 2 * PAD_X), float(ry + box_h)
            e.adv = float(baseline - base_in_box)
        else:
            e.x0, e.y0, e.x1, e.y1 = float(rx), float(ry), float(rx + gw + 2 * PAD_X), float(ry + gh)
            e.adv = float(baseline - asc)
        e.bx, e.by = SIDE_BEARING - 2 * PAD_X, 2.0
    return len(lat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dpc", default=r"D:\Games\A Plague Tale - Requiem\FONT\ENGLISH.DPC")
    ap.add_argument("--font", default=DEF_FONT)
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--no-latin", action="store_true",
                    help="skip restyling Latin/punct to David Libre")
    ap.add_argument("--no-shrink", action="store_true",
                    help="skip the em-shrink (clamping tall unused Arabic boxes) size test")
    args = ap.parse_args()

    if args.revert:
        import shutil
        if os.path.exists(args.dpc + BACKUP):
            shutil.copy2(args.dpc + BACKUP, args.dpc); print("reverted")
        else:
            print("no backup")
        return

    src = args.dpc + BACKUP if os.path.exists(args.dpc + BACKUP) else args.dpc
    D = DpcRepack(src)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}

    # ONE shared page cache + touched set across ALL fonts (they may share texture pages).
    page_arr = {}
    def load_page(tex):
        if tex not in page_arr:
            raw = byid[tex].body
            page_arr[tex] = [decode_alpha(bytearray(raw[:NPIX])),
                             decode_color(bytearray(raw[:NPIX])).astype(np.float32),
                             raw[NPIX:],
                             np.zeros((SIDE, SIDE), np.float32)]   # per-glyph ramp length
        return page_arr[tex]
    def page_alpha(tex):
        return load_page(tex)[0]

    print(f"font: {os.path.basename(args.font)} (thin) — injecting Hebrew into EVERY font")
    touched = {}
    done = []
    for oid, tag in FONT_OIDS.items():
        obj = byid.get(oid)
        if obj is None:
            print(f"  [{tag}] object missing — skip"); continue
        fz = FontsZ(obj.body)
        m2t = resolve_mat_textures(byid, fz)
        if not m2t:
            print(f"  [{tag}] textures not resolved — skip"); continue
        capH, baseline = font_metrics(fz, m2t, page_alpha)
        # ---- HEBREW BODY HEIGHT: target the Latin X-HEIGHT, not the cap. ----
        # Measured across all 7 shipped fonts (2026-07-12): SMALL_FONT (the English subtitle
        # font) has cap 'H' = 57 and lowercase 'o' = 41; BIG_ARABIC has cap 79 / 'o' 47.
        # Hebrew has NO lowercase — EVERY letter is full body height — while English text is
        # mostly lowercase. So Hebrew set at the CAP height carries far more visual mass and
        # reads as "much bigger" than the English beside it even at an equal cap. The
        # typographically correct match is Hebrew body ~= the Latin X-HEIGHT (~40px), which is
        # also why the previous 50px looked oversized.
        # ---- 🔑 EM-BOX SIZE LEVER (the RIGHT one). Atlas ink ALONE only changes SHARPNESS
        # (proven in-game: 18/29/36 px atlas ALL render at ~30 px screen — the engine locks the menu
        # size). The ONLY on-screen SIZE lever is the FILL: a smaller em glyph centred in a FIXED,
        # LARGER declared box renders at (em/BOX_H) x the fixed size = SMALLER, while the atlas glyph
        # stays big = SHARP. box HEIGHT is UNIFORM (=BOX_H, so size is consistent across letters);
        # box WIDTH stays tight (=glyph width, so the advance/spacing is correct — the missing fix
        # that made the old em-box "break spacing").
        inks = [min(capH, h) for h in (LADDER_INK if LADDER else (LADDER_INK[0],) * 3)]
        tgt = inks[0]                                   # Latin/digit restyle target size
        gsets = [render_set(args.font, fit_body(args.font, h), HEBREW) for h in inks]
        size = fit_body(args.font, inks[0])
        # 🔑 UNIFORM EM-BOX — the engine model, measured over six in-game builds:
        #        screen_ink = REQUESTED x ink_h / (MAX declared box height in the line)
        #   That explains every result so far: with a TIGHT box (box == ink) each line
        #   self-normalises (18/29/36 px atlas ALL rendered ~30 px = "the size never changes"),
        #   and the size then depends on WHICH letters a line happens to contain (a line with ל
        #   renders smaller than one without) = the inconsistency. ONE uniform box for every
        #   glyph fixes both: relative letter heights stay correct (ל tall, yod short, finals
        #   descend) AND the box height becomes the single honest SIZE knob.
        met = [(g.shape[0], asc) for gs in gsets for g, asc in gs.values()]
        MAX_ASC = max(asc for _gh, asc in met)                    # lamed
        MAX_DESC = max(gh - asc for gh, asc in met)               # final letters / qof
        BASE_IN_BOX = MAX_ASC + 1                                 # ONE baseline row for all
        BOX_H = BASE_IN_BOX + max(MAX_DESC, int(0.32 * tgt)) + 1  # + room for Latin descenders
        if BOX_H_FIX > BOX_H:
            # Pad the box SYMMETRICALLY and move the baseline down by the top pad, so `adv`
            # (= baseline - BASE_IN_BOX) absorbs it exactly: the glyph's on-screen position is
            # unchanged no matter which way the engine anchors the box — only the ratio
            # ink/BOX_H, i.e. the SIZE, moves.
            top_pad = (BOX_H_FIX - BOX_H) // 2
            BASE_IN_BOX += top_pad
            BOX_H = BOX_H_FIX
        _std = [asc for ch, (_g, asc) in gsets[0].items() if ch not in _HE_TALL + _HE_SHORT]
        _body = int(np.median(_std)) if _std else tgt
        _r = _body / BOX_H
        print(f"  [{tag}] body={_body} lamed={MAX_ASC} desc={MAX_DESC} BOX_H={BOX_H} "
              f"ratio={_r:.3f} -> menu label {32.5 * _r:.1f}px  title {60.0 * _r:.1f}px  "
              f"start-prompt {48.0 * _r:.1f}px   (raw 900p, MEASURED REQs)")
        max_bw = max(g.shape[1] for gs in gsets for g, _ in gs.values())
        slots = find_slots(fz, m2t, max_bw + 2 * PAD_X, BOX_H, 27)
        if len(slots) < 27:
            print(f"  [{tag}] only {len(slots)} slots for {max_bw+2}x{BOX_H} (capH={capH}) — SKIP")
            continue
        plan = [(slots[i], ch, (i % 3) if LADDER else 0) for i, ch in enumerate(HEBREW)]
        for e, ch, grp in plan:
            tex = m2t[e.mat]
            a, g, _tr, rmap = load_page(tex)
            glyph, ascent = gsets[grp][ch]
            gh, gw = glyph.shape
            # 🔴🔴 CLEAR THE **FULL ORIGINAL** BOX, not just the new (smaller) one. Measured on
            # the deployed em-box build: 27/27 glyphs kept 22,191 px of the slot's OWN Arabic
            # glyph alive just outside the new box — and because an em-box makes the engine
            # DOWNSCALE, its mip/bilinear tap reaches that far and drags the leftovers in as
            # the "dots" beside every letter. A tight box never showed it (no downscale, and
            # that code happened to clear the whole original box).
            ox0, oy0, ox1, oy1 = int(e.x0), int(e.y0), int(e.x1), int(e.y1)
            a[oy0:oy1, ox0:ox1] = 0
            g[oy0:oy1, ox0:ox1] = 0.0
            rmap[oy0:oy1, ox0:ox1] = 0.0
            gy = oy0 + BASE_IN_BOX - ascent              # every letter on ONE baseline
            a[gy:gy + gh, ox0 + PAD_X:ox0 + PAD_X + gw] = glyph
            # outline is a FRACTION of the glyph, so it scales with it (ramp/ink must stay at
            # the shipped Arabic's 0.152). Sizing it to the RENDERED height made it too thin.
            rmap[gy:gy + gh, ox0 + PAD_X:ox0 + PAD_X + gw] = ramp_len(inks[grp])
            blks = touched.setdefault(tex, set())
            for yy in range(oy0, oy1):
                for xx in range(ox0, ox1):
                    blks.add((yy // 4, xx // 4))
            e.cid = char_to_cid(ch)
            e.x0, e.y0 = float(ox0), float(oy0)
            e.x1, e.y1 = float(ox0 + gw + 2 * PAD_X), float(oy0 + BOX_H)  # +1px margin/side
            e.adv = float(baseline - BASE_IN_BOX)             # identical for every letter
            e.bx = SIDE_BEARING - 2 * PAD_X; e.by = 2.0   # box grew by 2*PAD_X -> pay it back
        if LADDER:
            for grp in (0, 1, 2):
                lets = "".join(ch for _, ch, gk in plan if gk == grp)
                print(f"  [ladder] group {'ABC'[grp]} ink={inks[grp]}px "
                      f"outline={ramp_len(inks[grp]):.1f}px  letters: {lets}")
        n_lat = 0
        if oid == BIG and not args.no_latin:             # restyle BIG_ARABIC's "silky" Latin
            # cap = tgt (the SAME size as the Hebrew body), NOT capH(79): rendering Latin/digits
            # at 79 overflowed the freed boxes -> shrink fallback -> the reported inconsistent
            # digit sizes, and mismatched the smaller Hebrew. Matching sizes fixes both.
            n_lat = repack_latin(fz, args.font, load_page, m2t, touched, baseline, tgt,
                                 box_h=BOX_H, base_in_box=BASE_IN_BOX)
        # ---- SIZE LEVER (the LAST untested one, added after proving size is NOT a per-glyph
        # metric / box / footer / descriptor field). English (SMALL_FONT) and Hebrew
        # (BIG_ARABIC) share the SAME subtitle widget + requested_pt yet render at DIFFERENT
        # sizes => the on-screen size DOES depend on the font, via an em/line-height the engine
        # DERIVES from the font's TALLEST declared glyph boxes. Visible Hebrew+Latin are already
        # <=50px, but ~100 UNUSED Arabic glyphs still declare ~90px boxes -> they inflate the em
        # -> every Arabic-slot line (incl. Hebrew subtitles) renders at the BIG em. Clamp every
        # remaining tall box (metrics ONLY; those glyphs are never displayed, no atlas edit).
        # If the em is metric-derived -> Hebrew shrinks; if it's pure external requested_pt ->
        # no change (which would finally PROVE the size is 100% in the game's UI data). ----
        if oid == BIG and not args.no_shrink:
            EM_CLAMP = 48
            heb_cids = {char_to_cid(ch) for ch in HEBREW}
            nclamp = 0
            for e in fz.entries:
                c = cid_to_char(e.cid)
                is_latin = bool(c) and len(c) == 1 and 0x21 <= ord(c) <= 0x7E
                if e.cid in heb_cids or is_latin:        # keep the VISIBLE glyphs untouched
                    continue
                if (e.y1 - e.y0) > EM_CLAMP:
                    e.y0 = e.y1 - EM_CLAMP               # shrink the invisible box to 48px tall
                    if (e.x1 - e.x0) > 40:
                        e.x1 = e.x0 + 40
                    e.adv = float(BASELINE - EM_CLAMP)
                    nclamp += 1
            print(f"  [BIG] em-shrink: clamped {nclamp} tall unused glyph-boxes -> {EM_CLAMP}px")
        obj.body = fz.build(); obj.dirty = True
        done.append(tag)
        print(f"  [{tag}] 27 Hebrew (capH={capH} baseline={baseline} size={size}) latin={n_lat}")

    # re-encode every touched block across all fonts' pages
    for tex, blks in touched.items():
        a, g, trailer, rmap = page_arr[tex]
        blks |= rebuild_colour(a, g, rmap, blks)   # outline = per-glyph ramp(dist-from-final-ink)
        gi = g.clip(0, 255).astype(np.uint8)
        raw = bytearray(byid[tex].body[:NPIX])
        bpr = SIDE // 4
        for (byk, bxk) in blks:
            o = (byk * bpr + bxk) * 16
            raw[o:o + 8] = enc_alpha(a[byk * 4:byk * 4 + 4, bxk * 4:bxk * 4 + 4])
            raw[o + 8:o + 16] = enc_color(gi[byk * 4:byk * 4 + 4, bxk * 4:bxk * 4 + 4])
        byid[tex].body = bytes(raw) + trailer
        byid[tex].dirty = True
    print(f"injected into fonts: {done}; re-encoded {len(touched)} pages")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ENGLISH_he.DPC")
    open(out, "wb").write(D.build())
    print("wrote", out)

    verify(out)
    # SAFETY: re-parse EVERY injected font from the built file; abort deploy if any broke.
    D2 = DpcRepack(out)
    byid2 = {o.oid: o for o in (list(D2.db_objs) + [o for _, o, _ in D2.fb_objs])}
    bad = []
    for oid, tag in FONT_OIDS.items():
        if tag not in done:
            continue
        try:
            fz2 = FontsZ(byid2[oid].body)
            nheb = sum(1 for e in fz2.entries
                       if (lambda c: c and 0x05D0 <= ord(c[0]) <= 0x05EA)(cid_to_char(e.cid)))
            if nheb < 27:
                bad.append(f"{tag}:{nheb}Heb")
        except Exception as ex:
            bad.append(f"{tag}:parsefail({ex})")
    if bad:
        print("ABORT deploy — injected fonts failed re-parse:", bad); return
    print(f"multi-font verify OK ({len(done)} fonts): {done}")
    if args.deploy:
        import shutil
        # 🔴 A RUNNING GAME MAKES A DEPLOY INVISIBLE — and the game is SINGLE-INSTANCE, so a
        # "restart" while one copy is alive starts a process that immediately EXITS and merely
        # re-focuses the OLD window. The font is read once at startup, so the user keeps looking
        # at whatever build was live when that instance began = "nothing changed", forever.
        # Worse, an ELEVATED instance cannot be closed from here (taskkill -> Access is denied).
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq APlagueTaleRequiem_x64.exe",
                            "/FO", "CSV", "/NH"], capture_output=True, text=True)
        if "APlagueTaleRequiem" in r.stdout:
            print("\n  🔴 THE GAME IS RUNNING. It reads the font ONCE at startup and it is\n"
                  "     single-instance, so relaunching now would just re-focus the old window\n"
                  "     and show the OLD font. CLOSE THE GAME COMPLETELY, then deploy again.\n")
        if not os.path.exists(args.dpc + BACKUP):
            shutil.copy2(args.dpc, args.dpc + BACKUP); print("backed up")
        shutil.copy2(out, args.dpc); print("DEPLOYED ->", args.dpc)


def verify(path):
    """Re-parse the built DPC, decode edited pages with PILLOW (GPU truth). Emit an
    alpha sheet, a colour-glow sheet, and a shader-sim (dark ink on parchment) so the
    weight/edge-softness/depth can be judged BEFORE deploying. Also prints my glyph's
    mid/solid AA ratio + stroke width to compare with the original (0.24 / 5-8px)."""
    D = DpcRepack(path)
    byid = {o.oid: o for o in (list(D.db_objs) + [o for _, o, _ in D.fb_objs])}
    fm = byid[BIG]; fz = FontsZ(fm.body)
    m2t = resolve_mat_textures(byid, fz)
    heb = sorted([e for e in fz.entries if 0xD790 <= e.cid <= 0xD7AA], key=lambda e: e.cid)
    print(f"VERIFY: {len(heb)} Hebrew entries")
    gpu = {tex: gpu_rgba(bytearray(byid[tex].body[:NPIX])) for tex in {m2t[e.mat] for e in heb}}
    cw, chh, pad = 70, 100, 6
    N = len(heb)
    alpha_sheet = Image.new("RGB", (N * (cw + pad), chh + pad * 2), (20, 20, 20))
    glow_sheet = Image.new("RGB", (N * (cw + pad), chh + pad * 2), (20, 20, 20))
    sim_sheet = Image.new("RGB", (N * (cw + pad), chh + pad * 2 + 16), (228, 223, 212))
    dr = ImageDraw.Draw(sim_sheet)
    x = pad; ok = 0; ratios = []; strokes = []
    for e in heb:
        px = gpu[m2t[e.mat]]
        crop = px[int(e.y0):int(e.y1), int(e.x0):int(e.x1)]
        a = crop[..., 3]; col = crop[..., 0]
        if (a > 200).sum() > 20:
            ok += 1
        mid = ((a > 30) & (a < 225)).sum(); solid = (a >= 225).sum()
        if solid:
            ratios.append(mid / solid)
        row = a[a.shape[0] // 2]; c = 0
        for v in row:
            if v >= 180: c += 1
            elif c: strokes.append(c); c = 0
        alpha_sheet.paste(Image.fromarray(a, "L").convert("RGB"), (x, pad))
        glow_sheet.paste(Image.fromarray(col, "L").convert("RGB"), (x, pad))
        # shader sim: dark ink shaped by alpha, darkened a touch more where the glow peaks
        af = a.astype(np.float32) / 255
        parch = np.array([228, 223, 212], np.float32)
        ink = np.array([40, 33, 26], np.float32)
        comp = parch[None, None] * (1 - af[..., None]) + ink[None, None] * af[..., None]
        sim_sheet.paste(Image.fromarray(comp.clip(0, 255).astype(np.uint8), "RGB"), (x, pad))
        dr.text((x, chh + pad), cid_to_char(e.cid), fill=(90, 70, 40))
        x += cw + pad
    pa = os.path.join(SC, "HEBREW_alpha.png"); alpha_sheet.save(pa)
    pg = os.path.join(SC, "HEBREW_glow.png"); glow_sheet.save(pg)
    ps = os.path.join(SC, "HEBREW_sim.png"); sim_sheet.save(ps)
    avg_ratio = sum(ratios) / max(1, len(ratios))
    med_stroke = sorted(strokes)[len(strokes) // 2] if strokes else 0
    print(f"  {ok}/27 solid; my AA mid/solid={avg_ratio:.2f} (orig 0.24) median stroke={med_stroke}px (orig 5-8)")
    print("  sheets:", ps)


if __name__ == "__main__":
    main()
