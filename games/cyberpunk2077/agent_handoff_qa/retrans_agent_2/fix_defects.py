"""Shared deterministic defect detection for the CP2077 fix-only flow.

A line is in the fix pool ONLY if it carries an OBJECTIVE, mechanically-provable
defect (foreign script in Hebrew text, a Hebrew<->Latin glued seam, or a
dangling/truncated tail). These are unambiguously broken, so a contributor can
NOT answer "OK" — the only valid output is a corrected Hebrew line, and
fix_merge re-checks that the SAME defect is gone. This is exactly the unfakeable
"translation shape" the Google agents do well, unlike open-ended review.
"""
import re

FOREIGN = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯぀-ヿĀ-ɏ]')
SEAM = re.compile(r'[א-ת][A-Za-z]|[A-Za-z][א-ת]')
HEB = re.compile(r'[א-ת]')
NIQQUD = re.compile(r'[֑-ׇ]')
DANGLING = re.compile(r'(?:^|\s)(?:ו|של|את|אל|על|עם|כי|אבל|או|גם|כדי|לפני|אחרי|בגלל|ב|ל|מ|ה|ש)$')


def strip_ctrl(s):
    return s[1:] if s and 0x01 <= ord(s[0]) <= 0x05 else s


def core(s):
    """Hebrew text with tags + {placeholders} removed — foreign letters INSIDE a
    <kiroshi l="rus" o="..."> tag are legit game data, not a translation defect."""
    return re.sub(r'<[^>]*>|\{[^}]*\}', '', strip_ctrl(s or ''))


def visible(s):
    return re.sub(r'<[^>]*>|\{[^}]*\}|%[#0-9.lhs%d]+|&[a-zA-Z#0-9]+;', '', strip_ctrl(s or '')).strip()


def defect_of(en, he):
    """Return the objective defect kind of a Hebrew line, or None if it's clean.
    (Clean here means 'no OBJECTIVE defect' — it may still be awkwardly phrased,
    which is the separate, judgment-only Opus pass.)"""
    c = core(he)
    if FOREIGN.search(c):
        return "foreign"        # German/Polish/Viet/... leaked into the Hebrew
    if SEAM.search(c):
        return "seam"           # גילherme / מטלFX — a broken half-transliteration
    v = visible(he)
    if v and DANGLING.search(v) and len(visible(en)) > 30:
        return "truncated"      # Hebrew ends on a dangling connector mid-thought
    return None
