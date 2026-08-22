"""Build the Corsair Cove NAME REGISTRY -- BEFORE any translation starts.

Standing project rule ([[verify-names-before-fleet-starts]] / [[name-registry-and-internet-check]]):
a glossary written from imagination damages as much as it fixes, and a name spelled three
different ways across a corpus is the #1 recurring consistency defect (RDR2, Plague Tale, SM2).
So the registry is built, oracle-checked and web-verified FIRST, then injected into every
translation batch and re-applied at MERGE, so a later correction fixes the whole corpus
without re-translating a single line.

TWO SOURCES, both evidence, neither guessed:

1. **The engine's OWN metadata.** Corsair Cove ships `Speaker`/`Addressee` columns, so the
   character list is a genuine CLOSED SET (20 names) -- not a regex guess over capitalised
   words. Nothing else in this project has had that.

2. **The game's OWN professional locales decide TRANSLATE vs TRANSLITERATE.** Russian is the
   ideal oracle because Cyrillic makes a transliteration visible at a glance:
       Rambullion -> Рамбуйон   (transliterated)  => Hebrew transliterates
       Raven      -> Ворон      (TRANSLATED)      => Hebrew must translate too
       Reaper     -> Жнец       (TRANSLATED)      => ditto
       Jonah      -> Иона / PL Jonasz  (the BIBLICAL form) => Hebrew must be יונה, not ג'ונה
   Getting any of those three from the English alone would have shipped a wrong name.

`--report` prints the oracle table for review; the committed `name_registry.json` is the
decided output. Re-run `--report` whenever the corpus is re-extracted.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
CORPUS = GAME / "extract" / "context_source.json"
OUT = GAME / "work" / "name_registry.json"

ORACLE_LANGS = ("ru", "pl", "de", "fr")

STOP = set(
    "The A An And Or But If You Your We Our They I It Is Are Was Be To Of In On At For With From "
    "This That These Those All Any No Not Can Will Would Should May Now Then When What Who How Why "
    "New Use Get Set Press Hold Complete Defeat Find Go Do Don Let Yes Ok OK Each Every Only More "
    "Less Next Back Close Open Start Stop Save Load Exit Menu Level Total Current Max Min".split())

PHRASE = re.compile(r"\b([A-Z][a-z']+(?:\s+(?:of|the|de|al|and|s)\s+)?(?:\s[A-Z][a-z']+)+)\b")


def load():
    return json.load(open(CORPUS, encoding="utf-8"))


def characters(d):
    """The engine's own closed set: every distinct Speaker / Addressee that is a real name."""
    c = collections.Counter()
    for v in d.values():
        for f in ("speaker", "addressee"):
            n = (v.get(f) or "").strip()
            # skip the group/role buckets and the rows where a Comment leaked one column left
            if not n or len(n) > 24 or "<" in n or n.lower() in {"self", "player", "crew", "guards", "pirates"}:
                continue
            if any(w in n.lower() for w in ("community", "captains", "crew", "soldiers", "island", "then ")):
                continue
            c[n] += 1
    return c


def phrases(d, chars):
    c = collections.Counter()
    for v in d.values():
        en = v.get("en") or ""
        if not en or en.isupper():
            continue
        for m in PHRASE.findall(en):
            w = m.split()
            if w[0] in STOP or all(x in chars for x in w):
                continue
            c[m] += 1
    return c


def oracle(d, term, want=1, maxlen=130):
    """Return sample (en, {lang: text}) lines containing `term`, for the review table."""
    pat = re.compile(r"\b" + re.escape(term) + r"\b")
    out = []
    for v in d.values():
        en = v.get("en") or ""
        if not pat.search(en) or len(en) > maxlen:
            continue
        r = v.get("refs") or {}
        if not r.get("ru"):
            continue
        out.append((en, {L: r.get(L, "") for L in ORACLE_LANGS}))
        if len(out) >= want:
            break
    return out


def report():
    d = load()
    chars = characters(d)
    print("=" * 78)
    print("CHARACTERS -- from the engine's own Speaker/Addressee columns (closed set)")
    print("=" * 78)
    for n, cnt in chars.most_common():
        s = oracle(d, n)
        ru = s[0][1]["ru"] if s else ""
        pl = s[0][1]["pl"] if s else ""
        print(f"\n  {n}   ({cnt} rows)")
        if s:
            print(f"     EN: {s[0][0][:100]}")
            print(f"     RU: {ru[:100]}")
            print(f"     PL: {pl[:100]}")
    ph = phrases(d, set(chars))
    print("\n" + "=" * 78)
    print("PLACES / FACTIONS / SHIPS -- top candidates")
    print("=" * 78)
    for n, cnt in ph.most_common(40):
        s = oracle(d, n)
        print(f"\n  {n}   ({cnt})")
        if s:
            print(f"     RU: {s[0][1]['ru'][:100]}")
            print(f"     DE: {s[0][1]['de'][:100]}")
    return 0


def main(argv):
    if "--report" in argv:
        return report()
    if not OUT.exists():
        print("no registry yet - run with --report, decide, then commit name_registry.json")
        return 1
    reg = json.load(open(OUT, encoding="utf-8"))
    terms = reg["terms"]
    print(f"registry: {len(terms)} terms")
    kinds = collections.Counter(t["kind"] for t in terms.values())
    print("by kind:", dict(kinds))
    modes = collections.Counter(t["mode"] for t in terms.values())
    print("by mode:", dict(modes))
    unver = [k for k, t in terms.items() if not t.get("source")]
    print("without a provenance note:", len(unver))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
