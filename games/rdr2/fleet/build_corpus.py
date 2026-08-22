# -*- coding: utf-8 -*-
"""Build the RDR2 fleet corpus: one row per line, EN + the game's own ARABIC.

New-Era doctrine says translate against every language the game itself ships. RDR2 is the thin
case: its RPF8 table of contents is TFIT-encrypted, so we cannot read Rockstar's French/Russian/…,
and the public English dump carries English only. What we DO have is Ko Games' professional
ARABIC mod — and for Hebrew that is the single most valuable reference there is: Arabic marks the
same distinctions Hebrew needs and English drops (أنتَ/أنتِ/أنتم = אתה/את/אתם, gendered verbs,
feminine ـة). So the panel is EN + AR, and AR is the gender oracle, not a tie-breaker.

The Arabic is stored VISUAL + presentation-form in the mod; `build_ct_strings.to_logical_arabic`
already converts it to readable logical order PER SEGMENT (reversing the whole string would
concatenate ~n~ segments and flip their order). We reuse that function rather than re-deriving it.

Output (what a worker reads):
    {key: {"en": str, "ar": str, "sec": <Hebrew visibility category>}}
ordered by VISIBILITY, so shard 0 is not "all the boring tail" — the first lines a stream touches
are the ones a player sees first.

    py fleet/build_corpus.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(GAME, "work"))

import build_ct_strings as B  # noqa: E402  (its loaders are the single source of truth)

# Same order the community pool uses — see CLAUDE.md "community-pool-by-category".
CAT_ORDER = ["ממשק ותפריטים", "פריטים וציוד", "כתוביות עלילה",
             "מסמכים ותוכן נוסף", "דיבורי רקע", "תוכן מקוון (RDR Online)"]


def main():
    en = json.load(io.open(os.path.join(GAME, "extract", "en_corpus.json"), encoding="utf-8"))
    ar = B.load_arabic()
    print(f"english : {len(en):,}")
    print(f"arabic  : {len(ar):,}")

    rows = []
    dropped = 0
    for k, v in en.items():
        if not B.is_translatable(k, v):
            dropped += 1
            continue
        rows.append((B.category(k, v), k, v))
    rank = {c: i for i, c in enumerate(CAT_ORDER)}
    rows.sort(key=lambda r: (rank.get(r[0], 99), r[1]))

    out = {}
    with_ar = 0
    for cat, k, v in rows:
        a = ar.get(k, "")
        if a:
            with_ar += 1
        out[k] = {"en": v, "ar": a, "sec": cat}

    path = os.path.join(HERE, "corpus.json")
    io.open(path, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
    print(f"dropped (untranslatable): {dropped:,}")
    print(f"corpus  : {len(out):,}   with arabic: {with_ar:,} "
          f"({with_ar / max(1, len(out)) * 100:.1f}%)")
    counts = {}
    for cat, _k, _v in rows:
        counts[cat] = counts.get(cat, 0) + 1
    for c in CAT_ORDER:
        if c in counts:
            print(f"   {c}: {counts[c]:,}")
    print("->", path)


if __name__ == "__main__":
    main()
