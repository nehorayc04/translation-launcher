#!/usr/bin/env python3
"""build_full.py — the REAL 217k-line RDR2 Hebrew corpus, deployed end to end.

Chain: fleet/hebrew.json (LOGICAL Hebrew, 217,433 entries) -> pre-wrap long values to the
proven splash-box budget (rdr2_rtl.WIDTH_SPLASH=110) -> UBA logical->visual -> KEY=value
LML override file -> drop into the already-proven Ko Games loader structure (work/legal/)
-> deploy to the live game.

LEGAL_SPLASH_* (4 keys) are excluded from the generic pass and rendered with the
pixel-precise `justify_visual_px` path build_legal.py already proved in-game (full
justification against the font's real glyph advances, not a character-count wrap).

Any value containing `=` is EXCLUDED (not overridden -> falls back to the base game's own
text for that one key). Rule: the LML `KEY = value` parser is documented (build_legal.py) as
breaking on an embedded `=`, "seen in-game". Measured: 77 of 217,433 entries carry one, every
single one is a `~INPUT_*|PromptId=X~` engine button-prompt token the fleet correctly left
untouched — never text we wrote. 0.035% of the corpus; skipping them is a strictly safer
default than risking any parser corruption of the surrounding lines for the sake of a handful
of short control-prompt strings ("Hold X to reel in") that are legible in English regardless.

Run:
    python build_full.py [--deploy]
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rdr2_text as R
from rdr2_rtl import (WIDTH_SPLASH, visible_len, wrap_logical, wrap_logical_vis,
                      wrap_visual_px)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.abspath(os.path.join(HERE, "..", "fleet"))
# The proven loader+font structure to reuse. ⚠️ This tree also carries
# lml/KGF/asset_replace/font_lib_efigs.gfx, and --deploy copies the WHOLE tree, so a text
# deploy silently reverts the font. Whenever rdr2_stencil_inject.py produces a new .gfx,
# copy it in here too -- otherwise the next build undoes the font work.
LEGAL_DIR = os.path.join(HERE, "legal")
OUT = os.path.join(HERE, "full")
GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2"

BUDGET = 13500
FACE = "Hapna Slab Serif  DemiBold"
LEGAL_KEYS = ("LEGAL_SPLASH_1", "LEGAL_SPLASH_1B", "LEGAL_SPLASH_2", "LEGAL_SPLASH_2B")

# 🔴 SHIP THE BOOT SPLASHES IN VANILLA ENGLISH (user's call, 2026-08-09: "תשאיר את זה באנגלית
# כמו המקורי ... ואז אחר כך נתקן את זה"). These four are dense legal paragraphs on the very
# first screen, they are the only surface that needs pre-wrapping + right-alignment, and they
# are the one place where a layout mistake is unmissable — so they are deliberately deferred
# rather than shipped imperfect.
#
# 🔑 OMIT the keys, do NOT write the English back in. An LML override file only overrides the
# keys it CONTAINS, so dropping them makes the game fall back to its own text, byte-for-byte —
# no risk of shipping the mojibake'd public-dump copy (which has `?` where U+2211 belongs and
# a stale `©2005-19`), and no `=`/token hazard. The corrected Hebrew stays in the spine, so
# turning this back on later starts from the improved text, not from the old one.
SHIP_LEGAL_ENGLISH = True

# 🔴🔴 A PARSED WIDGET STRING MUST SHIP IN ENGLISH. `0xE234DD49` is the alert's WHOLE button
# row in ONE string -- `~INPUT_FRONTEND_ACCEPT~ Yes ~INPUT_FRONTEND_CANCEL~ No` -- and the
# widget SPLITS it on the glyph tokens to build two buttons. Baking it VISUAL reorders it to
# `לא ~CANCEL~ כן ~ACCEPT~`, which starts with a LABEL instead of a token, so the parse fails
# and the row renders NOTHING AT ALL (not scrambled -- absent). Found by bisection after the
# text, the font, the glyph advances and LML itself were each ruled out by measurement; a
# 36-marker Latin ladder had shown nothing precisely BECAUSE overriding this key at all kills
# the row, whatever the content.
# Omitting the key makes the game draw its own row, exactly as if unmodded.
#
# ⚠️ Omitting 0xE234DD49 ALONE did NOT bring the row back, so it is not the (only) cause. The
# row is therefore drawn from SEPARATE per-button keys, and exactly one Yes/No pair lives in the
# same unverified .yldb set: 0xC4A4A05C ('Yes') and 0xC3881591 ('No'). Those two WERE in the
# 36-marker ladder and showed nothing -- but that ladder also carried a MALFORMED 0xE234DD49
# (its two glyph tokens got glued together), which on its own could have killed the row and
# masked them. So the ladder never actually cleared them.
#
# ✅ SHIPPING ENGLISH WAS THE SAFE FIX, NOT THE ONLY ONE. The engine is not refusing Hebrew --
# it is refusing a broken token skeleton. `rdr2_rtl.to_visual_row` pins every glyph where the
# game's own string has it and reverses ONLY the labels, so the parse survives AND the buttons
# read Hebrew. `scan_parsed_rows.py` rules each row from the data: `fix` when our value carries
# the SAME glyph multiset as the game's English, `omit` when it does not (a .yldb mis-pair whose
# CONTENT is wrong, so English is the only correct answer).
ROWS_JSON = os.path.join(HERE, "parsed_rows.json")

# 🔴🔴 THE LINE-ORDER INVERSION. The engine wraps in STORAGE order and we store VISUAL, so every
# value the engine has to wrap ITSELF renders bottom-line-first: the sentence begins on the last
# line and climbs. The build DID pre-wrap — but at WIDTH_SPLASH (110 chars), the width of the boot
# splash, the widest surface in the game. Hebrew lines run 40-70 chars, so the wrap almost never
# fired and almost everything inverted.
# `measure_boxes.py` derives the real per-family box from two independent oracles that agree
# (Rockstar's own authored `~n~` -> median 36 chars; Ko Games' shipping Arabic RTL mod, which hit
# this same bug and hand-wrapped 1,173 strings -> median 37). See box_widths.json.
BOXES_JSON = os.path.join(HERE, "box_widths.json")
_FAM = __import__("re").compile(r"^([A-Z]{2,}[0-9]*)_")


def _family(key):
    if key.startswith("0x"):
        return "<hash>"
    m = _FAM.match(key)
    return m.group(1) if m else key.split("_")[0][:12]


def load_boxes():
    if not os.path.exists(BOXES_JSON):
        return 40, {}
    d = json.load(open(BOXES_JSON, encoding="utf-8"))
    return d.get("default", 40), d.get("families", {})

# still English on purpose: 2 bare labels kept out until the row itself is confirmed, so the
# next launch moves exactly one variable.
OMIT_KEYS = {
    "0xC4A4A05C",   # 'Yes' - a bare label, no tokens; restored once the row is confirmed
    "0xC3881591",   # 'No'
}

# A/B diagnostic (2026-08-05), RESOLVED 2026-08-07: the boot legal splash is a DIFFERENT
# renderer from the pause-menu/HUD. Half the strings shipped VISUAL and half LOGICAL, and
# the in-game screenshots decided it -- see the note under the table.
# ✅ ALL FOUR VISUAL — and the authority for that is the USER'S EYES, not my reading.
# 🔴 I called the direction three times from a screenshot and was wrong every time.
# [[hebrew-screenshot-transcription-trap]] is explicit: transcription returns READING order,
# not pixel order, so a mirrored line and a correct line come out identical — and that cuts
# BOTH ways. Twice I read "correct" on a mirrored screen; the third time I read "mirrored" on
# a screen the user then confirmed was fine, and flipping screen 1 to LOGICAL on that reading
# would have BROKEN a working screen. When the user has looked at the pixels, that is the
# measurement; my transcription is not evidence at all and must not overrule it.
# The engine draws in storage order on both splashes, exactly like the HUD (proofs #1-#7).
# ⚠️ Never justify these: justification pads a string the engine then draws in storage order.
LEGAL_MODE = {
    "LEGAL_SPLASH_1":  "visual",
    "LEGAL_SPLASH_1B": "visual",
    "LEGAL_SPLASH_2":  "visual",
    "LEGAL_SPLASH_2B": "visual",
}
# 🔴🔴 RAGGED, NOT JUSTIFIED — and the reason is a hard limit, not a preference.
# We can only stretch a line by inserting whole SPACE characters, and a space in this face is
# 58 units of a 13,500-unit measure. A greedy wrap already fills 93-99 % of the measure, so the
# leftover is 5-15 spaces spread over ~20 gaps: `divmod` then hands +1 space to 15 of the 18
# gaps and 0 to the rest, which is a line full of irregular double-gaps. Measured on the
# shipped build: SPLASH_1 line 1 had 15 multi-space runs, SPLASH_1B line 5 had 11 — and the
# holes land INSIDE Latin brand names too (`Rockstar  Games,  Inc.`), which reads as broken.
# There is no sub-space granularity to fix that with, so flush-both-edges is unreachable here.
# Right-alignment gives a perfectly flush RIGHT edge (where a Hebrew reader starts) with single
# spaces everywhere; only the left edge is ragged, which is how RTL prose is normally set.
# `wrap_visual_px` also BALANCES the wrap, so the left edge stays close to even.


def render_legal_visual(logical):
    """Pre-wrap + right-align each ~n~ block on its own (VISUAL storage). See the note above:
    justification is NOT usable on this surface — whole-space granularity tears rivers."""
    return "~n~".join(
        "" if not b.strip() else wrap_visual_px(b.strip(), BUDGET, FACE)
        for b in logical.split("~n~")
    )


def render_legal_logical(logical):
    """Plain LOGICAL storage: just pre-wrap each block so the engine's own wrap can't
    invert the line order; NO to_visual/justify -- for the A/B test above."""
    return "~n~".join(
        "" if not b.strip() else wrap_logical(b.strip(), WIDTH_SPLASH)
        for b in logical.split("~n~")
    )


# 🔴 RE-OPENED 2026-08-07: the player reports BOTH boot warnings mirrored, which contradicts
# the note above. A screenshot cannot settle it — transcribing Hebrew from an image returns
# READING order, not PIXEL order, so a mirrored line and a correct line transcribe IDENTICALLY
# ([[hebrew-screenshot-transcription-trap]]). The only reliable instrument is an A/B PAIR of
# the SAME word stored both ways on ONE screen, where exactly one of them can be the readable
# word. `# 🔴🔴 THE A/B WAS DECIDED WITH THE ONE INSTRUMENT THIS PROJECT FORBIDS: reading Hebrew off
# a screenshot. Transcription returns READING order, not PIXEL order, so a mirrored line
# and a correct line transcribe IDENTICALLY -- I called it LOGICAL, shipped it, and the
# user reported the splash still mirrored. See [[hebrew-screenshot-transcription-trap]].
# THE RELIABLE INSTRUMENT IS A POSITION QUESTION, and DIGITS answer it: a digit is
# LTR-strong, so "which numeral is on the RIGHT" needs no reading and no judgement.
#   logical `1 בדיקה 9` + an RTL base  -> 1 on the RIGHT, 9 on the LEFT
#   logical `1 בדיקה 9` + NO bidi      -> 1 on the LEFT,  9 on the RIGHT
# Screen 1 carries SPLASH_1 (logical) over SPLASH_1B (visual); screen 2 the same for 2/2B,
# so ONE launch answers both screens and both storage modes.
# ✅ SETTLED — and NOT by reading the Hebrew, which is the instrument that got this wrong
# twice. PUNCTUATION POSITION is the reliable read: with the text stored LOGICAL the splash
# rendered `,גוריד תואלבט` — the comma glued to the START of a word — while the block stored
# VISUAL rendered `אנשים, מקומות, חברות,` with every comma at the END and `(EULA)` correctly
# parenthesised. A mirrored line cannot produce correct punctuation placement by accident.
# ⇒ the boot splash runs NO bidi, exactly like the HUD (proofs #1-#7). One answer for the
# whole game again; the earlier "the splash runs bidi" note was the anomaly, not the rule.
# ⚠️ Do NOT justify these: justification pads a string the engine then draws in storage order.
LEGAL_AB = None


def render_legal(key, logical):
    ab = LEGAL_AB.get(key) if LEGAL_AB else None
    if ab:
        marker, mode = ab
        # the marker is emitted RAW, exactly as written, so the mode it demonstrates is the
        # mode the bytes are in — no transform may touch it or the test proves nothing.
        body = (render_legal_logical(logical) if mode == "logical"
                else render_legal_visual(logical))
        return f"{marker}~n~{body}"
    mode = LEGAL_MODE.get(key, "visual")
    return render_legal_logical(logical) if mode == "logical" else render_legal_visual(logical)


# 🔴🔴 NEVER EMIT A CODEPOINT THE FONT WAS NOT GIVEN. This game's face is the Latin
# `font_lib_efigs` Scaleform font with exactly **27 Hebrew LETTERS** injected (U+05D0-05EA) —
# no Hebrew PUNCTUATION and no format controls. Anything else in the Hebrew block renders as
# a tofu box mid-word, which looks like a broken translation rather than a missing glyph.
# An audit of the full 231k-line corpus found: geresh ׳ ×225, gershayim ״ ×30, maqaf ־ ×35,
# invisible bidi controls ×112, U+FFFD mojibake ×51, non-breaking hyphen ×19.
# The ASCII equivalents are visually identical to a reader and are guaranteed to exist in a
# Latin font. (The IRON RULE deliberately spares the maqaf because in some games it is
# correct — here the FONT decides, exactly as its note says.)
_FONT_MAP = {
    "׳": "'",   # geresh      -> apostrophe   (ג׳קסון)
    "״": '"',   # gershayim   -> quote
    "־": "-",   # maqaf       -> hyphen
    "‑": "-",   # non-breaking hyphen
    "„": '"',   # low-9 quote
    "℅": "c/o",
}
# invisible controls: the engine does NO bidi (we bake VISUAL), so these can only ever be a
# tofu box or a stray advance. U+FFFD is source mojibake — drop it rather than draw a box.
_FONT_DROP = "​‌‍‎‏‪‫‬‭‮⁠﻿� "

def _FOREIGN_LETTER(c):
    """A letter from a script the font has never heard of = mojibake the guard let through
    (one Devanagari char survived in 231k lines). On screen it is a box, never content."""
    o = ord(c)
    return (0x0370 <= o <= 0x058F or 0x0600 <= o <= 0x08FF or 0x0900 <= o <= 0x1CFF
            or 0x2E80 <= o <= 0xA4CF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF)



def font_safe(v):
    if not isinstance(v, str):
        return v
    for a, b in _FONT_MAP.items():
        if a in v:
            v = v.replace(a, b)
    if any(c in v for c in _FONT_DROP):
        v = "".join(c for c in v if c not in _FONT_DROP)
    # a stray letter from a script the font has never heard of is mojibake the guard let
    # through (one Devanagari char survived in 231k lines) — a box on screen, never content.
    if any(_FOREIGN_LETTER(c) for c in v):
        v = "".join(c for c in v if not _FOREIGN_LETTER(c))
    return v


def main():
    deploy = "--deploy" in sys.argv

    heb = json.load(open(os.path.join(FLEET, "hebrew.json"), encoding="utf-8"))

    # Lines the original corpus never had. It came from a public English dump covering
    # 93.9% of the keys, so the rest shipped in English; unpacking the game's archives
    # exposed 28,101 real strings that were missing (the mission-board text in the user's
    # screenshots among them). They are keyed by the game's own 0xHASH, which is exactly
    # what the LML override file takes, so they merge straight in.
    # BISECT HOOK: RDR2_SKIP_MISSING=1 ships ONLY the 217k keys that came from the public
    # English dump, leaving out the 28k recovered from the game's own .yldb. Those 28k are the
    # unverified set (their English pairing is ~27% wrong), and a marker ladder proved the
    # prompt row is driven by a key that is NOT in any English map I have -- which is exactly
    # the shape of a .yldb key. One launch splits 245k into 217k / 28k.
    extra_path = os.path.join(FLEET, "hebrew_missing.json")
    if os.environ.get("RDR2_SKIP_MISSING"):
        print("!! BISECT: hebrew_missing.json EXCLUDED (28k .yldb keys)")
        extra_path = ""
    if extra_path and os.path.exists(extra_path):
        extra = json.load(open(extra_path, encoding="utf-8"))
        new = {k: v for k, v in extra.items() if k not in heb and v}
        heb.update(new)
        print(f"merged {len(new)} newly-translated lines from hebrew_missing.json")

    # DIAGNOSTIC HOOK: a probe build (build_yesno_probe.py) points this at a {key: value} file
    # whose values are pure-Latin markers, so ONE launch names the key a widget really reads.
    # Applied AFTER the merge and BEFORE font_safe/RTL so the markers ride the normal pipeline.
    ovr = os.environ.get("RDR2_OVERRIDE_JSON")
    if ovr and os.path.exists(ovr):
        o = json.load(open(ovr, encoding="utf-8"))
        heb.update(o)
        print(f"!! DIAGNOSTIC override: {len(o)} keys from {os.path.basename(ovr)}")

    # parsed button rows -- ruled from the data by scan_parsed_rows.py, never by hand
    row_fix, row_omit = set(), set()
    if os.path.exists(ROWS_JSON):
        for k, meta in json.load(open(ROWS_JSON, encoding="utf-8")).items():
            (row_fix if meta.get("verdict") == "fix" else row_omit).add(k)

    # 🔴 CORRECTION (this was wrong in an earlier build): RDR2 has NO Arabic locale at all --
    # `extract/game_text{,_v2}/` cover american/brazilian/chinese(simp+trad)/french/german/
    # italian/japanese/korean/mexican/polish/russian/spanish, and none of that is Arabic. The
    # "Arabic slot" language elsewhere in this project is CP2077/SM2/WD2's real Rockstar/CDPR
    # locale hijack -- it does NOT apply here. RDR2's mechanism is Ko Games' LML loader patching
    # KEY=value pairs directly on top of the game's OWN active (American/English) text; a key we
    # never write into `lml/tranar/Ko Games Studio.gxt2` is simply not intercepted, so the game
    # shows its OWN vanilla bytes for it -- which, with no Arabic option to select, is plain
    # ENGLISH (exactly the LEGAL_SPLASH_* fallback below, for the same reason).
    dropped = [k for k in (OMIT_KEYS | row_omit) if heb.pop(k, None) is not None]
    if dropped:
        print(f"omitted (mis-paired / bare widget labels): {sorted(dropped)}")
        print(f"  -> these fall back to the game's OWN vanilla English, not Arabic")
    row_fix &= set(heb)
    print(f"parsed button rows: {len(row_fix)} glyph-pinned, {len(row_omit)} left English")

    heb = {k: font_safe(v) for k, v in heb.items()}

    with_eq = {k: v for k, v in heb.items() if "=" in v}
    heb = {k: v for k, v in heb.items() if "=" not in v}
    print(f"loaded {len(heb) + len(with_eq)} entries, "
          f"excluded {len(with_eq)} with '=' in value (LML parser safety)")

    legal_recs = []
    for k in LEGAL_KEYS:
        v = heb.pop(k, None)                       # always POP: never fall into the generic pass
        if v is None or SHIP_LEGAL_ENGLISH:
            continue
        legal_recs.append({"kind": "entry", "key": k, "val": render_legal(k, v)})
    if SHIP_LEGAL_ENGLISH:
        print(f"legal splashes: SHIPPING VANILLA ENGLISH "
              f"({len(LEGAL_KEYS)} keys omitted from the override)")
    else:
        print("LEGAL_MODE (A/B):", LEGAL_MODE)

    # pre-wrap to the MEASURED box so the engine never wraps (and never inverts) our lines.
    # A parsed row is exempt: its layout is the widget's business, not ours.
    box_default, box_fam = load_boxes()
    wrapped = 0
    for k, v in list(heb.items()):
        if k in row_fix:
            continue
        w = box_fam.get(_family(k), box_default)
        if visible_len(v) <= w and "~n~" not in v:
            continue
        nv = wrap_logical_vis(v, w)
        if nv != v:
            heb[k] = nv
            wrapped += 1
    print(f"pre-wrapped {wrapped:,} values to their measured box "
          f"(default {box_default} visible chars, {len(box_fam)} families measured)")

    generic_recs = R.to_map(R.build_hebrew([], heb, wrap_width=None, row_keys=row_fix))
    generic_recs = [{"kind": "entry", "key": k, "val": v} for k, v in generic_recs.items()]

    all_recs = legal_recs + generic_recs
    for r in all_recs:
        assert "=" not in r["val"], f"{r['key']}: '=' slipped through"

    # a parsed row is only safe if its token SEQUENCE survived the bake byte-for-byte -- a moved
    # glyph is exactly the failure that made every warning dialog lose its buttons, and it is
    # invisible in-game until someone opens that screen.
    _tok = __import__("re").compile(r"~[^~]*~")
    by_key = {r["key"]: r["val"] for r in all_recs}
    # ⚠️ a row whose glyph carries `|PromptId=...` is dropped by the '=' guard above, so it ships
    # the game's own English -- correct, but it is no longer ours to verify.
    shipped = sorted(row_fix & set(heb) & set(by_key))
    for k in shipped:
        before, after = _tok.findall(heb[k]), _tok.findall(by_key[k])
        assert before == after, f"{k}: row tokens moved {before} -> {after}"
    print(f"  verified: token order preserved on {len(shipped)} parsed rows "
          f"({len(row_fix) - len(shipped)} dropped by the '=' guard, they ship English)")

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for root, _dirs, files in os.walk(LEGAL_DIR):
        rel = os.path.relpath(root, LEGAL_DIR)
        dst_root = OUT if rel == "." else os.path.join(OUT, rel)
        os.makedirs(dst_root, exist_ok=True)
        for f in files:
            if rel == "lml/tranar" and f.endswith(".gxt2"):
                continue  # we write the real text file below
            shutil.copy2(os.path.join(root, f), os.path.join(dst_root, f))

    text = ("# RED DEAD REDEMPTION 2 Hebrew — full translation "
            f"({len(all_recs)} keys)\n\n" + R.serialise(all_recs) + "\n")
    gxt2_path = os.path.join(OUT, "lml", "tranar", "Ko Games Studio.gxt2")
    with open(gxt2_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print(f"built {len(all_recs)} entries ({len(legal_recs)} legal + {len(generic_recs)} generic)")
    print("  gxt2 size:", os.path.getsize(gxt2_path), "bytes")
    print("  out dir:", OUT)

    if deploy:
        for rel_path in (
            "dinput8.dll", "ScriptHookRDR2.dll", "vfs.asi", "ModManager.Core.dll",
            "ModManager.NativeInterop.dll", "NLog.dll", "lml.ini",
        ):
            shutil.copy2(os.path.join(OUT, rel_path), os.path.join(GAME, rel_path))
        for rel_path in (
            "lml/mods.xml", "lml/patterns.dat",
            "lml/KGF/install.xml", "lml/KGF/asset_replace/font_lib_efigs.gfx",
            "lml/tranar/install.xml", "lml/tranar/Ko Games Studio.gxt2",
        ):
            parts = rel_path.split("/")
            dst = os.path.join(GAME, *parts)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(OUT, *parts), dst)
        print("deployed to:", GAME)


if __name__ == "__main__":
    main()
