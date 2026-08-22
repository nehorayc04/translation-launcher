"""Shared token/placeholder helpers + validators for the VirtualDJ handoff."""
import re

# printf-style + VirtualDJ format specs that MUST survive translation verbatim.
#   %i %s %d %f %x  %02d  %%  %2F  %full %HH %MM %SS %DD
TOKEN_RE = re.compile(r"%%|%2F|%[0-9]*[a-zA-Z]")

NIQQUD_RE = re.compile(r"[֑-ׇ]")
HEB_RE = re.compile(r"[א-ת]")
# foreign scripts we must never leak into Hebrew (Arabic, CJK, Cyrillic, Greek, Thai...)
FOREIGN_RE = re.compile(
    r"[؀-ۿЀ-ӿͰ-Ͽ฀-๿"
    r"぀-ヿ一-鿿가-힯]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def tokens(s):
    return sorted(TOKEN_RE.findall(s or ""))


def is_nameish(en):
    """A source that legitimately stays Latin in Hebrew: brand/code/short label
    with no real translatable words (or a single proper noun)."""
    words = LATIN_WORD_RE.findall(en)
    if not words:
        return True                      # pure symbols/numbers/placeholders
    # a single no-space token that is a domain / url / filename / path
    e = en.strip()
    if " " not in e and ("." in e or "/" in e or ":" in e):
        return True
    # technical units/abbreviations stay Latin (kbps, dB, Hz, ms, fps...)
    UNITS = {"kbps", "mbps", "bpm", "db", "hz", "khz", "ms", "fps", "rpm",
             "kb", "mb", "gb", "px", "dpi", "khz", "bit"}
    if len(words) == 1 and words[0].lower() in UNITS:
        return True
    # a single camelCase/brand token with any internal capital (iTunes, iDJPool,
    # RekordBox, GeniusDJ) legitimately stays Latin
    if len(words) == 1 and any(c.isupper() for c in words[0]):
        return True
    # <=2 words that are all Capitalized/ALLCAPS -> brand-ish
    if len(words) <= 2 and all(w[0].isupper() for w in words):
        return True
    return False


def validate(en, he):
    """Return (ok, reason). Enforces the hard structural rules; the merge gate
    uses this so an agent can't cheat by copying English or dropping tokens."""
    he = (he or "").strip()
    if he == "":
        return False, "empty"
    if NIQQUD_RE.search(he):
        return False, "niqqud"
    if FOREIGN_RE.search(he):
        return False, "foreign-script"
    if tokens(en) != tokens(he):
        return False, f"token-mismatch en={tokens(en)} he={tokens(he)}"
    if not HEB_RE.search(he):
        # no Hebrew is only OK when the source itself is a name/code
        if is_nameish(en):
            return True, "ok-name-passthrough"
        return False, "no-hebrew-on-prose"
    # untranslated leak: identical to English while English has real words
    if he == en.strip() and LATIN_WORD_RE.search(en):
        return False, "identical-to-english"
    return True, "ok"
