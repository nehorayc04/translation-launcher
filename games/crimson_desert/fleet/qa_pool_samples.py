# -*- coding: utf-8 -*-
"""Independent QA over lines the POOL actually accepted - the 1% spot-check, for gen 2.

WHY IT IS NOT REDUNDANT WITH THE WORKER'S OWN GUARD: the guard runs inside the worker, on
the worker's own understanding of the line. This re-checks the SHIPPED result from the
outside, against the English that was actually sent, and it is the only place that can catch
a guard that is wrong (a rule that accepts what it should reject is invisible to itself).
That is exactly how the word-by-word Hebrew and the token-only classes were caught before.

Source: `samples.jsonl`, which every pool worker appends to on submit. Read-only.

Run:  python qa_pool_samples.py [path-to-samples.jsonl] [--show N]
"""
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cd_nim  # noqa: E402  (STRUCT / NIQ / the brain glossary - one source of truth)

# A single Hebrew prefix letter standing as its OWN word before a Hebrew word is impossible in
# real Hebrew (prefixes are glued) - it is the signature of word-by-word "translation".
WORDBYWORD = re.compile(r"(?<![א-ת])([מהלובשכ])\s+(?=[א-ת])")
LONGDASH = re.compile("[\u2010-\u2015\u2212\u2e3a\u2e3b\ufe58\ufe63\uff0d]")
HEB = re.compile("[א-ת]")
LAT = re.compile("[A-Za-z]")


def foreign(s):
    """Any letter that is neither Hebrew nor Latin - a leaked reference language."""
    out = set()
    for ch in s:
        if not ch.isalpha():
            continue
        n = unicodedata.name(ch, "")
        if not (n.startswith("HEBREW") or n.startswith("LATIN")):
            out.add(unicodedata.name(ch, "?").split()[0])
    return out


def check(en, he):
    """[(code, detail)] - empty means the line is clean."""
    bad = []
    if not he.strip():
        return [("empty", "")]
    if cd_nim.NIQ.search(he):
        bad.append(("niqqud", ""))
    f = foreign(he)
    if f:
        bad.append(("foreign", ",".join(sorted(f))))
    te, th = sorted(cd_nim.STRUCT.findall(en)), sorted(cd_nim.STRUCT.findall(he))
    if te != th:
        bad.append(("tokens", f"{te} -> {th}"))
    if he.strip() == en.strip() and HEB.search(en) is None and en.strip():
        bad.append(("copy-en", ""))
    if not HEB.search(he) and LAT.search(cd_nim.STRUCT.sub("", en) or ""):
        bad.append(("no-hebrew", ""))
    if LONGDASH.search(he):
        bad.append(("long-dash", ""))       # IRON RULE: only a plain hyphen ever ships
    if WORDBYWORD.search(he):
        bad.append(("word-by-word", WORDBYWORD.search(he).group(0)))
    s = cd_nim.SEAM.search(he)
    if s:
        # half-transliteration (`בדropkick`) - the worker's guard now rejects these, so a hit
        # here means a line that was banked BEFORE the gate existed
        bad.append(("hebrew-latin-seam", s.group(0)))
    # a translation many times longer than its source is the runaway/rambling signature
    if len(en) > 20 and len(he) > 3.0 * len(en):
        bad.append(("length", f"{len(en)}->{len(he)}"))
    return bad


def main():
    path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else r"C:\cdw\samples.jsonl"
    show = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 8
    rows, seen = [], set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("id") in seen:
                continue
            seen.add(r.get("id"))
            rows.append(r)
    tally, flagged = {}, []
    for r in rows:
        bad = check(r.get("en") or "", r.get("he") or "")
        for code, det in bad:
            tally[code] = tally.get(code, 0) + 1
        if bad:
            flagged.append((r, bad))
    ok = len(rows) - len(flagged)
    print(f"lines checked: {len(rows)}   clean: {ok} ({100*ok/max(1,len(rows)):.1f}%)   flagged: {len(flagged)}")
    for code, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"   {code:14} {n}")
    for r, bad in flagged[:show]:
        print(f"\n  [{','.join(c for c, _ in bad)}] {r.get('prov')} {r.get('id')}")
        print(f"    EN: {(r.get('en') or '')[:150]}")
        print(f"    HE: {(r.get('he') or '')[:150]}")
        for c, d in bad:
            if d:
                print(f"    -> {c}: {d[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
