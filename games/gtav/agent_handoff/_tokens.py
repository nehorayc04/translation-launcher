"""Shared GTA V token helpers for the agent-handoff QA loop (stdlib only).

A GTA V gxt2 string can carry:
  * tilde tokens  ~r~ ~s~ ~h~ ~n~ ~a~ ~1~ ~HUD_COLOUR_X~ ~INPUT_FRONTEND_ACCEPT~ ...
    (color/style/newline/button/blip codes) -- MUST survive verbatim + same multiset.
  * HTML-ish tags <C>...</C>, <font ...> (rare) -- preserve verbatim.
  * printf-ish refs %s %d (rare in gxt2) -- preserve.
The translator works in LOGICAL Hebrew; visual reversal is applied later at BUILD time,
NOT here. These helpers only check that the STRUCTURE (tokens) is preserved.

All character classes use \\u escapes (no literal non-ASCII in the source) to stay
encoding-safe.
"""
import re

# ~...~ token (inner has no '~'); <...> tag; %spec.
TOKEN_RE = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]")

# Hebrew letters: base block U+05D0..U+05EA + final forms already inside, plus the
# Alphabetic Presentation Forms U+FB1D..U+FB4F.
HEB_RE = re.compile("[֐-׿יִ-ﭏ]")
# Niqqud / cantillation combining marks we forbid.
NIQQUD_RE = re.compile("[֑-ׇֽֿׁׂׅׄ]")
# Foreign letter scripts that must never leak into a Hebrew/Latin translation.
FOREIGN_RE = re.compile(
    "[Ѐ-ӿ"      # Cyrillic
    "؀-ۿ"       # Arabic
    "฀-๿"       # Thai
    "぀-ヿ"       # Hiragana/Katakana
    "㐀-鿿"       # CJK
    "가-힯]"      # Hangul
)


def tokens(s):
    """Multiset (sorted list) of structural tokens in s."""
    return sorted(TOKEN_RE.findall(s or ""))


def has_hebrew(s):
    return bool(HEB_RE.search(s or ""))


def has_niqqud(s):
    return bool(NIQQUD_RE.search(s or ""))


def foreign_chars(s):
    """Foreign-script letters that leaked in (Cyrillic/CJK/Arabic/Thai/Hangul...)."""
    return FOREIGN_RE.findall(s or "")


def real_word(en):
    """True if the English source has a real lowercase word >=2 letters (so it SHOULD
    become Hebrew). Names/codes/numbers (DLC, ISO, 60FPS, Trevor) have none -> may stay
    Latin (the universal name/code passthrough rule)."""
    return bool(re.search(r"[a-z]{2,}", en or ""))
