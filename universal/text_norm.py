#!/usr/bin/env python3
"""
text_norm.py - deterministic text normalisation applied to EVERY Hebrew translation
in this project, for every game, now and in the future.

🔴 IRON RULE (user, 2026-08-02): **always the plain ASCII hyphen `-`, never a long
dash `—`.** It is a hard, deterministic rule with exactly one correct answer, so it
belongs in the BUILD PIPELINE, not in a style guide a translator or an agent has to
remember. A rule that lives only in a document WILL be violated -- an LLM emits an
em dash by reflex, and a human copy-editing Hebrew does too.
(First raised on Anno 1800 on 2026-07-30 and re-stated as universal here.)

WHY the pipeline and not a QA check: a QA check reports a defect that then has to be
fixed by hand N times; a normalisation makes the defect impossible. Same reasoning as
the SignalRGB lesson -- when the same defect class recurs across batches, move the fix
into the pipeline.

WHAT IS REPLACED (every dash that is not the ASCII hyphen):
    U+2010 HYPHEN              U+2011 NON-BREAKING HYPHEN
    U+2012 FIGURE DASH         U+2013 EN DASH
    U+2014 EM DASH             U+2015 HORIZONTAL BAR
    U+2E3A TWO-EM DASH         U+2E3B THREE-EM DASH
    U+FE58 SMALL EM DASH       U+FE63 SMALL HYPHEN-MINUS
    U+FF0D FULLWIDTH HYPHEN-MINUS
Replacement is ONE FOR ONE: a decorative run (`—— רמות ——`) keeps its shape, it just
becomes `-- רמות --`. Only the character changes, never the string's length or layout.

WHAT IS **NOT** TOUCHED:
  * U+05BE HEBREW MAQAF -- a real Hebrew punctuation mark with its own job
    (`בין-לאומי`), not a "long dash". It is also a separate rendering question:
    on some engines the maqaf sits too high (see the Witcher 3 notes), so if it ever
    looks wrong, that is a FONT decision, made per game, not this rule.
  * U+2212 MINUS SIGN inside a real mathematical expression is not a dash either, but
    in game text it is virtually always meant as a hyphen, so it IS normalised.

CLI:
    python text_norm.py selftest
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# every dash-like codepoint EXCEPT the ASCII hyphen and the Hebrew maqaf (U+05BE)
LONG_DASHES = "‐‑‒–—―−⸺⸻﹘﹣－"
_TABLE = {ord(c): "-" for c in LONG_DASHES}


def normalize_dashes(s):
    """Every long/typographic dash -> the plain ASCII hyphen, ONE FOR ONE.

    🔴 Deliberately NOT a run-collapse. A repeated dash is usually a decorative rule a
    translator drew on purpose (`—— רמות ——` heads a VirtualDJ section), and collapsing
    it to a single hyphen silently redesigns the UI. The rule is about WHICH CHARACTER,
    not about how many - so only the character changes and the string's shape survives.
    (U+2E3A/U+2E3B are single codepoints for a two-/three-em dash, so they still map to
    exactly one hyphen, which is correct.)"""
    if not s:
        return s
    return s.translate(_TABLE)


def has_long_dash(s):
    return bool(s) and any(c in LONG_DASHES for c in s)


def scan(values):
    """Return the (index, value) of every entry still carrying a long dash --
    the QA net behind the normalisation, for auditing an already-built corpus."""
    return [(i, v) for i, v in enumerate(values) if has_long_dash(v)]


def selftest():
    cases = [
        ("שלום — עולם", "שלום - עולם"),
        ("טווח 0–100", "טווח 0-100"),
        ("דו‑קרב", "דו-קרב"),                      # non-breaking hyphen
        ("א ⸺ ב", "א - ב"),                        # two-em dash IS one codepoint
        ("א——ב", "א--ב"),                          # a decorative run keeps its shape
        ("כבר-תקין", "כבר-תקין"),                  # ASCII hyphen untouched
        ("בין־לאומי", "בין־לאומי"),                # MAQAF must survive
        ("", ""),
        (None, None),
    ]
    ok = 0
    for src, exp in cases:
        got = normalize_dashes(src)
        good = got == exp
        ok += good
        print(("PASS " if good else "FAIL ") + repr(src) + " -> " + repr(got))
    good = has_long_dash("א — ב") and not has_long_dash("א - ב") and not has_long_dash("בין־לאומי")
    ok += good
    print(("PASS " if good else "FAIL ") + "has_long_dash (maqaf is not a long dash)")
    total = len(cases) + 1
    print("\n%d/%d" % (ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
