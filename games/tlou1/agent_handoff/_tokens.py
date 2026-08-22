#!/usr/bin/env python3
r"""
_tokens.py - standalone token/validation helpers for the TLOU Part I handoff.
Self-contained (no repo imports) so an isolated agent can run get/merge.

A valid Hebrew line must PRESERVE the exact multiset of markup tags + island
tokens, carry NO niqqud, NO foreign script, and actually contain Hebrew (unless
the source is a proper-noun / code / label with fewer than 2 real lowercase words
-> then it may stay Latin). It must not be left byte-identical to the English on
real prose (anti-cheat).
"""
import re

# grammar mirrors games/tlou1/work/tlou_rtl.py (keep in sync)
_MARKUP = r"</?font[^>]*>|<br\s*/?>|<break\s*/?>|</?hang>|<[^<>]+>"
_ISLAND = r"\|[^|]+\||\[[^\[\]]*\]|%[#0-9.+\- ]*[sdiufFgGxXeEoc%]|\{[^{}]*\}|&[a-zA-Z]+;"
TOKEN_RE = re.compile("(?:" + _MARKUP + ")|(?:" + _ISLAND + ")")

HEB = re.compile(r"[א-ת]")
NIQQUD = re.compile(r"[֑-ׇ]")


def tokens(s):
    return sorted(m.group(0) for m in TOKEN_RE.finditer(s))


def _has_foreign(s):
    for ch in s:
        if not ch.isalpha():
            continue
        o = ord(ch)
        if 0x41 <= o <= 0x7A:      # Latin basic
            continue
        if 0xC0 <= o <= 0x17F:     # Latin-1 + Latin Extended-A (accents)
            continue
        if 0x5D0 <= o <= 0x5EA:    # Hebrew
            continue
        return True
    return False


def is_name_or_code(en):
    core = TOKEN_RE.sub(" ", en)
    words = re.findall(r"[A-Za-z]+", core)
    real_lower = [w for w in words if any(c.islower() for c in w)]
    return len(real_lower) < 2


def validate(en, he):
    """-> (ok: bool, reason: str)."""
    if he is None or not str(he).strip():
        return False, "empty"
    he = str(he)
    if NIQQUD.search(he):
        return False, "niqqud"
    if _has_foreign(he):
        return False, "foreign_script"
    if tokens(he) != tokens(en):
        return False, "token_mismatch"
    if not HEB.search(he):
        return (True, "name_passthrough") if is_name_or_code(en) else (False, "no_hebrew_on_prose")
    if he.strip() == en.strip() and not is_name_or_code(en):
        return False, "identical_to_english"
    return True, "ok"
