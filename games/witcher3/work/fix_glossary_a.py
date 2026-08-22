# -*- coding: utf-8 -*-
"""Track A — deterministic pre-launch fixes on fleet/hebrew.json.

1. GLOSSARY  — wrong/nonsense core UI terms, each guarded by the ENGLISH source
               (so a word is only swapped where the EN really uses that term).
2. BIDI      — strip stray U+202A..U+202E / U+200E / U+200F control chars. The
               engine ignores bidi controls for Hebrew, and a leftover RLO makes
               the line render MIRRORED in-game.
3. WITCHER   — normalise the 106 transliteration spellings to the dominant
               canonical form: standalone "ויטצ'ר", after a prefix "וויטצ'ר"
               (word-initial vav doubles after a prefix — the 507-hit majority).
               Words already using "מכשף" are left alone (valid choice).

    py fix_glossary_a.py           # dry-run report, writes nothing
    py fix_glossary_a.py --apply   # backup + atomic write
"""
import json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.join(HERE, "..")
HEB = os.path.join(GAME_DIR, "fleet", "hebrew.json")
EN = os.path.join(GAME_DIR, "extract", "en.json")

# (wrong, right, english-guard) — guard is a case-insensitive substring of the EN source
GLOSSARY = [
    ("תחליבים", "שיקויים", "potion"),
    ("תחלילים", "שיקויים", "potion"),
    ("תחליב",  "שיקוי",   "potion"),
    ("נוזלים",  "שיקויים", "potion"),
    ("נוזל",    "שיקוי",   "potion"),
    ("שומנים",  "שמנים",   "oil"),
    ("תססים",   "מרקחות",  "decoction"),
    ("השתקעות", "מדיטציה", "meditation"),
    ("מטוגנים", "מוטגנים", "mutagen"),
    ("מטגנים",  "מוטגנים", "mutagen"),
    ("חיוות",   "חיוניות", "vitality"),
    ("חיווי",   "חיוניות", "vitality"),
    ("אינסטנט", "סיבולת",  "stamina"),
    ("טוקסיציות", "רעילות", "toxicity"),
    ("טרופי",   "גביע",    "trophy"),
    ("מטען",    "ציוד",    "inventory"),
]

BIDI = "‎‏‪‫‬‭‮"
BIDI_RE = re.compile("[" + BIDI + "]")

# --- witcher transliteration normalisation -------------------------------
# Built as an EXPLICIT token->token map (reviewable) rather than an in-place regex:
# 'ו' is BOTH a valid prefix ("and") and the stem's first letter, so a naive
# regex re-prefixes an already-correct token (ויטצ'ר -> ווויטצ'ר).
PRE_LETTERS = "הלבמכש"          # unambiguous prefixes (NOT 'ו')
TOKEN_RE = re.compile(r"[֐-ת']+")
STEM_END_RE = re.compile(r"ט[שצ]'?ר$")


def canon_token(tok):
    """Return the canonical spelling for a witcher token, or None to leave it alone."""
    suf = ""
    for s in ("יות", "ים", "ית"):
        if tok.endswith(s):
            suf, tok = s, tok[: -len(s)]
            break
    m = STEM_END_RE.search(tok)
    if not m:
        return None
    head = tok[: m.start()]
    if not head:
        return None
    # explicit blacklist: real words that merely END like the stem
    if "בומבו" in head:
        return None
    # AMBIGUOUS: a leading 'וו' may be conjunction+stem — never touch it.
    if head.startswith("וו"):
        return None
    pre, i = "", 0
    while i < len(head):
        c = head[i]
        if c in PRE_LETTERS:
            pre += c
            i += 1
        elif c == "ו" and i + 1 < len(head) and head[i + 1] in PRE_LETTERS:
            pre += c
            i += 1
        else:
            break
    rest = head[i:]
    # whatever is left must be only the stem's vowel letters, else bail out
    if not rest or set(rest) - set("וי"):
        return None
    core = "וויטצ'ר" if pre else "ויטצ'ר"
    return pre + core + suf


def build_witcher_map(he):
    """Scan every value, return {wrong_token: canonical_token} for real changes only."""
    seen = {}
    for v in he.values():
        for tok in TOKEN_RE.findall(v):
            if "ט" not in tok or not ("צ'ר" in tok or "טשר" in tok):
                continue
            if tok in seen:
                continue
            seen[tok] = canon_token(tok)
    return {t: c for t, c in seen.items() if c and c != t}


def main(apply_it):
    he = json.load(open(HEB, encoding="utf-8"))
    en = json.load(open(EN, encoding="utf-8"))

    wmap = build_witcher_map(he)
    print("--- witcher spelling map (%d variants normalised) ---" % len(wmap))
    for a, b in sorted(wmap.items()):
        print(f"  {a:16} -> {b}")
    print()
    wre = re.compile("(?<![֐-ת'])(" + "|".join(
        re.escape(t) for t in sorted(wmap, key=len, reverse=True)) + ")(?![֐-ת'])") if wmap else None

    stats = {"glossary": 0, "bidi": 0, "witcher": 0}
    per_term = {}
    changed = {}
    samples = []

    for k, v in he.items():
        if not isinstance(v, str) or not v:
            continue
        orig = v
        e = en.get(k)
        e_low = e.lower() if isinstance(e, str) else ""

        # 1. glossary (english-guarded)
        for bad, good, guard in GLOSSARY:
            if bad in v and guard in e_low:
                n = v.count(bad)
                v = v.replace(bad, good)
                per_term[bad] = per_term.get(bad, 0) + n
                stats["glossary"] += n

        # 2. stray bidi controls
        if BIDI_RE.search(v):
            stats["bidi"] += len(BIDI_RE.findall(v))
            v = BIDI_RE.sub("", v)

        # 3. witcher spelling — only where the ENGLISH really says "witcher",
        #    so look-alike words (bumbotcher, …) are never touched.
        if wre is not None and "ט" in v and "witcher" in e_low:
            v2 = wre.sub(lambda m: wmap[m.group(1)], v)
            if v2 != v:
                stats["witcher"] += 1
                v = v2

        if v != orig:
            changed[k] = v
            if len(samples) < 20:
                samples.append((e if isinstance(e, str) else "", orig, v))

    print("=== TRACK A — deterministic pre-launch fixes ===")
    print(f"strings changed: {len(changed)} of {len(he)}")
    print(f"  glossary replacements : {stats['glossary']}")
    print(f"  bidi controls stripped: {stats['bidi']}")
    print(f"  witcher spellings fixed: {stats['witcher']}")
    print()
    print("--- per glossary term ---")
    for bad, good, _ in GLOSSARY:
        if per_term.get(bad):
            print(f"  {bad:12} -> {good:10} {per_term[bad]:5}")
    print()
    print("--- samples ---")
    for e, a, b in samples:
        print(f"  EN : {e[:70]}")
        print(f"  was: {a[:90]}")
        print(f"  now: {b[:90]}")
        print()

    if not apply_it:
        print("(dry-run) nothing written. re-run with --apply")
        return

    bak = HEB + ".bak.trackA." + time.strftime("%Y%m%d_%H%M%S")
    with open(bak, "w", encoding="utf-8") as f:
        json.dump(he, f, ensure_ascii=False)
    he.update(changed)
    tmp = HEB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(he, f, ensure_ascii=False)
    os.replace(tmp, HEB)
    print(f"APPLIED. backup: {os.path.basename(bak)}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
