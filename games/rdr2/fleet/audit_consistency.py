# -*- coding: utf-8 -*-
"""Measure RDR2 translation consistency + accuracy on whatever is banked so far.

Answers the only question that matters for a fleet: is the SAME English term coming back as the
SAME Hebrew everywhere? Anything it prints under "DIVERGENT" is a candidate line for
name_fixes.json — grow that file from THIS output, never from imagination.

    py fleet/audit_consistency.py
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
corpus = json.load(io.open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))
heb = json.load(io.open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
reg = json.load(io.open(os.path.join(HERE, "name_registry.json"), encoding="utf-8"))

STRUCT = re.compile(r'~[^~]*~|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+')
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힯Ѐ-ӿ]')
HEBLET = re.compile(r'[א-ת]')
LOWER = re.compile(r'[a-z]{2,}')

_PREFIX = "והבלמשכ"


def _present(want, text):
    """Is the canonical term in the text, allowing normal Hebrew inflection?

    A raw substring test flags correct Hebrew as a violation: מסכה becomes מסכת in the construct
    state and פרס becomes הפרס/ופרס with a prefix. Compare each canonical WORD on its stem and
    allow a single attached prefix letter, or the compliance number is noise.
    """
    for w in want.split():
        stem = w[:-1] if len(w) > 3 and w[-1] in "הת" else w
        if stem in text:
            continue
        if any(p + stem in text for p in _PREFIX):
            continue
        return False
    return True


print(f"banked {len(heb):,} / {len(corpus):,}\n")

# ---- structural -----------------------------------------------------------------------------
tok = [k for k in heb if sorted(STRUCT.findall(heb[k]))
       != sorted(STRUCT.findall(corpus.get(k, {}).get("en", "")))]
niq = [k for k in heb if NIQ.search(heb[k])]
fgn = [k for k in heb if FOREIGN.search(heb[k])]
cpy = [k for k, v in heb.items()
       if len(v) > 12 and v.strip() == corpus.get(k, {}).get("en", "").strip()]
noheb = [k for k, v in heb.items()
         if LOWER.search(STRUCT.sub(" ", corpus.get(k, {}).get("en", ""))) and not HEBLET.search(v)]
print("STRUCTURAL")
for lbl, xs in (("token mismatch", tok), ("niqqud", niq), ("foreign script", fgn),
                ("copy-EN", cpy), ("no Hebrew on prose", noheb)):
    print(f"  {lbl:22} {len(xs):6,}" + (f"   e.g. {xs[0]}" if xs else ""))

# ---- glossary compliance --------------------------------------------------------------------
terms = {}
for g in ("characters", "places", "factions", "systems", "gear"):
    terms.update({k: v for k, v in (reg.get(g) or {}).items() if k and v})
print("\nGLOSSARY COMPLIANCE (lines whose English holds a canonical term)")
miss = collections.Counter()
tot = collections.Counter()
for k, v in heb.items():
    en = corpus.get(k, {}).get("en", "")
    for t, want in terms.items():
        if re.search(r"\b" + re.escape(t) + r"\b", en):
            tot[t] += 1
            if not _present(want, v):
                miss[t] += 1
bad = [(t, miss[t], tot[t]) for t in tot if miss[t]]
bad.sort(key=lambda x: -x[1])
if not bad:
    print("  every canonical term present where expected")
for t, m, n in bad[:20]:
    print(f"  {t:24} missing in {m:4}/{n:<5} (want «{terms[t]}»)")

# ---- one English term, many Hebrew spellings --------------------------------------------------
print("\nDIVERGENT SPELLINGS (same English name -> different Hebrew) — feed these to name_fixes")
HEWORD = re.compile(r"[א-ת'׳\"״]{3,}")
seen = collections.defaultdict(collections.Counter)
for k, v in heb.items():
    en = corpus.get(k, {}).get("en", "")
    for t in terms:
        if re.search(r"\b" + re.escape(t) + r"\b", en) and len(t.split()) == 1:
            for w in HEWORD.findall(v):
                seen[t][w] += 1
shown = 0
for t, c in seen.items():
    variants = [w for w, n in c.most_common(6) if n >= 2]
    canon_he = terms[t]
    odd = [w for w in variants if w != canon_he and abs(len(w) - len(canon_he)) <= 2
           and w[:2] == canon_he[:2]]
    if odd:
        print(f"  {t:20} canonical «{canon_he}»  also seen: {', '.join(odd[:4])}")
        shown += 1
if not shown:
    print("  none detected at this sample size")
