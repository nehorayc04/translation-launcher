# -*- coding: utf-8 -*-
"""Derive the SM2 New-Era-2 REVIEW worker from the HARDENED Skyrim translate worker.

Why derive instead of editing the old `sm2qa_nim.py` in place: that file predates every fix
made on 2026-08-07 and has NONE of them (verified marker-by-marker) — no hard wall-clock
timeout around the blocking urlopen (a DNS stall hangs a stream for minutes with no strike),
no per-line-length panel budget (a book-scale line builds a quarter-million-character prompt
that can never be answered), no transport-failure ceiling (such a line is then re-served every
pass FOREVER, which is what pinned 15 of 21 streams at 0/min), no edge-whitespace repair, and
a `min(4000, ...)` output ceiling that silently truncates long answers.

Re-run this whenever skyrim_nim.py gains a fix, so the two never drift.
Every replacement is asserted, so a silent no-op is impossible.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "games", "skyrim", "fleet", "skyrim_nim.py")
DST = os.path.join(HERE, "sm2ne2_nim.py")

s = open(SRC, encoding="utf-8").read()
n = 0


def rep(old, new, count=1):
    global s, n
    assert s.count(old) >= count, f"MISSING anchor ({s.count(old)}x): {old[:90]!r}"
    s = s.replace(old, new, count)
    n += 1


# ── identity ──────────────────────────────────────────────────────────────────────────────
rep('"""Skyrim translator worker — New-Era, six-language panel.',
    '"""Marvel\'s Spider-Man 2 — New-Era-2 REVIEW worker (derived from skyrim_nim.py).\n\n'
    'MONOTONIC: the line is ALREADY translated and shipped. The worker may only FIX a genuine\n'
    'error; anything it is not sure about comes back unchanged. Every guard below is written to\n'
    'fail CLOSED (keep the current Hebrew), because a review that degrades a good line is worse\n'
    'than a review that misses a bad one.\n\n'
    'out_<prov>.json = {id: {"he": <hebrew>, "iss": ok|gender|phrasing|slang|error|foreign}}')
rep('Run: python skyrim_nim.py <groq|sambanova|nim>',
    'Run: python sm2ne2_nim.py <groq|sambanova|nim>')
rep('return "skyrim_nim" in (out or "")', 'return "sm2ne2_nim" in (out or "")')
rep('SKIP = os.path.join(HERE, f"cc_skip{_SUF}.json")',
    'SKIP = os.path.join(HERE, f"sm2ne2_skip{_SUF}.json")')

# ── the reference panel: SM2 ships 10 locales, and the review needs the CURRENT Hebrew ─────
rep('PANEL = ("ru", "pl", "de", "fr", "es", "it")',
    'PANEL = ("ar", "ru", "pl", "de", "fr", "it", "es", "es-mx", "pt")')
rep('PANEL_SLIM = ("ru", "pl")', 'PANEL_SLIM = ("ar", "ru", "pl")')

# ── tokens: SM2\'s <ts="a;b"> timing tags and the &rlm; RTL anchors are LOAD-BEARING ────────
rep('STRUCT = re.compile(r"<[^<>]{1,80}>|\\{[^{}]{0,80}\\}")',
    '# SM2 tokens: the <ts="a;b"> timing tags (order-bearing — they bind text to audio), any\n'
    '# other markup tag, the &rlm; RTL anchors the build depends on, [TOKEN]/{VALUE}, printf.\n'
    'STRUCT = re.compile(r\'<[^<>]{1,120}>|&[a-zA-Z]{2,8};|\\{[^{}]{0,80}\\}\'\n'
    '                    r\'|\\[[A-Z0-9_]{1,40}\\]|%[#0-9.*+-]*[a-zA-Z]\')')

# ── the review prompt ─────────────────────────────────────────────────────────────────────
old_s1 = s[s.index('S1 = ("You are a senior Hebrew localizer for The Elder Scrolls'):
            s.index('def _en(v):')]
rep(old_s1, '''S1 = ("You are a senior Hebrew localization EDITOR for Marvel's Spider-Man 2 (modern-day "
      "New York: Peter Parker and Miles Morales, fast banter, mission dialogue, story cutscenes). "
      "Each item gives: 'en' = the English source, 'he' = the Hebrew ALREADY SHIPPING, and the "
      "game's own professional translations ('ar' EGYPTIAN COLLOQUIAL, 'ru', 'pl', 'de', 'fr', "
      "'it', 'es', 'es-mx', 'pt'). Those other languages are your GROUND TRUTH for what English "
      "hides.\\n"
      "REVIEW each line. If 'he' is already correct, fluent and complete, RETURN IT UNCHANGED "
      "with iss=ok. That is the expected outcome for most lines. Only change a line for a REAL "
      "defect:\\n"
      "  gender  - wrong addressee/speaker gender or number. ADDRESSEE: Arabic إنتَ/عايز/فاهم -> "
      "אתה ; إنتِ/عايزة/ـكِ -> את ; أنتم/إنتوا -> אתם. Polish -leś->אתה, -łaś->את, wy->אתם. "
      "Russian ты+…л->אתה, ты+…ла->את. SPEAKER: Russian я …-л/-ла, Polish -łem/-łam - match the "
      "Hebrew 1st person and NEVER turn a 1st/3rd-person verb into 2nd person.\\n"
      "  FORMAL-YOU TRAP: Russian 'вы' / Italian 'voi' / Spanish 'usted' addressed to ONE person "
      "is FORMAL SINGULAR, not plural - Hebrew stays אתה/את. Only a TRUE plural (Arabic "
      "أنتم/إنتوا) becomes אתם.\\n"
      "  error   - a clear mistranslation against 'en'.\\n"
      "  phrasing- stiff/literal Hebrew where natural modern spoken Hebrew is meant.\\n"
      "  foreign - leftover English/Arabic/other-script words that should be Hebrew.\\n"
      "HARD RULES: keep the SAME meaning. Keep EVERY token byte-for-byte and in the same order "
      "and count - the <ts=\\"a;b\\"> timing tags, &rlm; RTL anchors, <span>/<i>/<br>, {VALUE}, "
      "[TOKEN], %d/%s. Keep NUMBERS. Keep canonical names (ספיידרמן, מיילס, פיטר, מרי ג'יין, "
      "הארי, מיי, ונום, קרייבן, הלטאה, העקרב, הנשר, החתולה השחורה, מיסטריו, סאנדמן, טומסטון). "
      "NO niqqud. Store LOGICAL Hebrew - never reverse letters. Use the plain hyphen '-', never "
      "a long dash. If 'gender_hint' is given it was derived from the game's own Arabic/Russian "
      "morphology - trust it over your own reading.\\n"
      "Output ONLY JSON {id:{\\"he\\":<hebrew>,\\"iss\\":<ok|gender|phrasing|slang|error|foreign>}} "
      "with exactly the same ids as the input.")


''')

# ── payload: carry the current Hebrew + the hint ───────────────────────────────────────────
rep('''    if v.get("gendered"):
        p["gender_note"] = "this line has a gender-dependent form in the game's own translations"
    return p''',
    '''    # the line under review, and the deterministic morphological hint the adapter derived
    p["he"] = _cur(v)
    if v.get("gender_hint"):
        p["gender_hint"] = v["gender_hint"]
    if v.get("speaker"):
        p["speaker"] = v["speaker"]
    return p


def _cur(v):
    """The Hebrew currently shipping. multilang_review stores `he` as [fv, mv]; SM2 has one
    string per id, so the two slots are identical and either is the line."""
    if not isinstance(v, dict):
        return ""
    h = v.get("he")
    if isinstance(h, list):
        return (h[0] or (h[1] if len(h) > 1 else "") or "").strip()
    return (h or "").strip()''')

open(DST, "w", encoding="utf-8").write(s)
print(f"wrote {DST}  ({n} replacements, all anchors matched)")
